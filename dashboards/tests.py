from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from blogs.models import Blog, Category
from dashboards.models import Feedback, Profile


class EditorOwnershipTests(TestCase):
    def setUp(self):
        self.editor_group, _ = Group.objects.get_or_create(name='Editor')
        self.editor = User.objects.create_user(username='editor', password='pass1234')
        self.other_editor = User.objects.create_user(username='other-editor', password='pass1234')
        self.manager = User.objects.create_user(username='manager', password='pass1234', is_staff=True)

        self.editor.groups.add(self.editor_group)
        self.other_editor.groups.add(self.editor_group)

        self.editor_category = Category.objects.create(category_name='Editor Category', owner=self.editor)
        self.other_category = Category.objects.create(category_name='Other Category', owner=self.other_editor)
        self.shared_category = Category.objects.create(category_name='Legacy Category')

        image = SimpleUploadedFile('test.jpg', b'filecontent', content_type='image/jpeg')
        self.editor_post = Blog.objects.create(
            title='Editor Post',
            slug='editor-post-1',
            category=self.editor_category,
            author=self.editor,
            featured_image=image,
            short_description='short',
            blog_body='body',
            status='Draft',
        )
        other_image = SimpleUploadedFile('test2.jpg', b'filecontent', content_type='image/jpeg')
        self.other_post = Blog.objects.create(
            title='Other Post',
            slug='other-post-2',
            category=self.other_category,
            author=self.other_editor,
            featured_image=other_image,
            short_description='short',
            blog_body='body',
            status='Draft',
        )

    def test_editor_only_sees_own_posts(self):
        self.client.force_login(self.editor)

        response = self.client.get(reverse('posts'))

        posts = list(response.context['posts'])
        self.assertEqual(posts, [self.editor_post])

    def test_editor_cannot_edit_other_users_post(self):
        self.client.force_login(self.editor)

        response = self.client.get(reverse('edit_post', args=[self.other_post.id]))

        self.assertEqual(response.status_code, 403)

    def test_editor_can_see_all_categories(self):
        self.client.force_login(self.editor)

        response = self.client.get(reverse('categories'))

        categories = list(response.context['categories'])
        self.assertCountEqual(categories, [self.editor_category, self.other_category, self.shared_category])

    def test_new_category_is_owned_by_creator(self):
        self.client.force_login(self.editor)

        response = self.client.post(reverse('add_category'), {'category_name': 'Fresh Category'})

        self.assertRedirects(response, reverse('categories'))
        category = Category.objects.get(category_name='Fresh Category')
        self.assertEqual(category.owner, self.editor)

    def test_editor_cannot_edit_other_users_category(self):
        self.client.force_login(self.editor)

        response = self.client.get(reverse('edit_category', args=[self.other_category.id]))

        self.assertEqual(response.status_code, 403)

    def test_editor_post_form_only_shows_owned_categories(self):
        self.client.force_login(self.editor)

        response = self.client.get(reverse('add_post'))

        categories = list(response.context['form'].fields['category'].queryset)
        self.assertEqual(categories, [self.editor_category])

    def test_manager_can_see_all_categories(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse('categories'))

        categories = list(response.context['categories'])
        self.assertCountEqual(categories, [self.editor_category, self.other_category, self.shared_category])


class ProfileTests(TestCase):
    def test_profile_is_created_with_user(self):
        user = User.objects.create_user(username='profile-user', password='pass1234', email='profile@example.com')

        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_user_can_update_own_profile(self):
        user = User.objects.create_user(username='owner', password='pass1234', email='owner@example.com')
        self.client.force_login(user)

        response = self.client.post(
            reverse('edit_my_profile'),
            {
                'first_name': 'Owner',
                'last_name': 'User',
                'email': 'owner-updated@example.com',
                'bio': 'Writes about product and engineering.',
            },
        )

        self.assertRedirects(response, reverse('my_profile'))
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Owner')
        self.assertEqual(user.last_name, 'User')
        self.assertEqual(user.email, 'owner-updated@example.com')
        self.assertEqual(user.profile.bio, 'Writes about product and engineering.')

    def test_my_profile_page_is_read_only_and_edit_page_exists(self):
        user = User.objects.create_user(username='reader', password='pass1234', email='reader@example.com')
        self.client.force_login(user)

        profile_response = self.client.get(reverse('my_profile'))
        edit_response = self.client.get(reverse('edit_my_profile'))

        self.assertEqual(profile_response.status_code, 200)
        self.assertContains(profile_response, 'Edit Profile')
        self.assertNotContains(profile_response, 'Save Profile')
        self.assertEqual(edit_response.status_code, 200)

    def test_user_can_save_profile_with_existing_own_email(self):
        user = User.objects.create_user(username='same-email', password='pass1234', email='same@example.com')
        self.client.force_login(user)

        response = self.client.post(
            reverse('edit_my_profile'),
            {
                'first_name': 'Same',
                'last_name': 'Email',
                'email': 'same@example.com',
                'bio': 'Keeps the same email.',
            },
        )

        self.assertRedirects(response, reverse('my_profile'))
        user.refresh_from_db()
        self.assertEqual(user.email, 'same@example.com')
        self.assertEqual(user.profile.bio, 'Keeps the same email.')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_registration_can_store_optional_profile_image(self):
        image = SimpleUploadedFile(
            'avatar.gif',
            (
                b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
                b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00'
                b'\x00\x02\x02D\x01\x00;'
            ),
            content_type='image/gif',
        )

        response = self.client.post(
            reverse('register'),
            {
                'email': 'newuser@example.com',
                'username': 'newuser',
                'first_name': 'New',
                'last_name': 'User',
                'password1': 'ComplexPass123!',
                'password2': 'ComplexPass123!',
                'profile_image': image,
            },
        )

        user = User.objects.get(username='newuser')
        self.assertRedirects(response, reverse('verify_wait', args=[user.id]))
        self.assertTrue(user.profile.profile_image.name.startswith('profiles/'))


class FeedbackTests(TestCase):
    def test_guest_can_submit_feedback(self):
        response = self.client.post(
            reverse('feedback'),
            {
                'name': 'Guest User',
                'email': 'guest@example.com',
                'feedback_type': 'Suggestion',
                'subject': 'Better navigation',
                'message': 'The mobile navigation could use a quick feedback link.',
                'page_url': '/some-page/',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        feedback = Feedback.objects.get(subject='Better navigation')
        self.assertIsNone(feedback.user)
        self.assertEqual(feedback.status, 'New')

    def test_logged_in_feedback_is_attached_to_user(self):
        user = User.objects.create_user(username='feedback-user', password='pass1234', email='feedback@example.com')
        self.client.force_login(user)

        response = self.client.post(
            reverse('feedback'),
            {
                'name': 'Feedback User',
                'email': 'feedback@example.com',
                'feedback_type': 'Bug',
                'subject': 'Broken state',
                'message': 'A button feels off on mobile.',
                'page_url': '/dashboard/',
            },
        )

        self.assertRedirects(response, reverse('feedback'))
        feedback = Feedback.objects.get(subject='Broken state')
        self.assertEqual(feedback.user, user)

    def test_manager_can_view_dashboard_feedback_page(self):
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        manager = User.objects.create_user(username='manager-viewer', password='pass1234', email='manager@example.com', is_staff=True)
        manager.groups.add(manager_group)
        Feedback.objects.create(
            name='Guest User',
            email='guest@example.com',
            feedback_type='General feedback',
            subject='General note',
            message='This is helpful.',
        )

        self.client.force_login(manager)
        response = self.client.get(reverse('dashboard_feedback'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'General note')

    def test_editor_cannot_view_dashboard_feedback_page(self):
        editor_group, _ = Group.objects.get_or_create(name='Editor')
        editor = User.objects.create_user(username='editor-viewer', password='pass1234', email='editor@example.com')
        editor.groups.add(editor_group)

        self.client.force_login(editor)
        response = self.client.get(reverse('dashboard_feedback'))

        self.assertEqual(response.status_code, 403)

    def test_superuser_can_edit_feedback_from_dashboard_page(self):
        superuser = User.objects.create_superuser(username='root', password='pass1234', email='root@example.com')
        feedback = Feedback.objects.create(
            name='Guest User',
            email='guest@example.com',
            feedback_type='Bug',
            subject='Needs review',
            message='Please update the status.',
        )

        self.client.force_login(superuser)
        response = self.client.post(
            reverse('edit_feedback', args=[feedback.id]),
            {
                'name': feedback.name,
                'email': feedback.email,
                'feedback_type': feedback.feedback_type,
                'subject': feedback.subject,
                'message': feedback.message,
                'page_url': feedback.page_url,
                'status': 'Reviewed',
            },
        )

        self.assertRedirects(response, reverse('dashboard_feedback'))
        feedback.refresh_from_db()
        self.assertEqual(feedback.status, 'Reviewed')
