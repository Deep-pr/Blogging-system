from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone
from urllib.parse import urlparse

from blogs.models import AuthorFollow, Blog, Category, ContentReport, PendingRegistration
from blog_main.forms import RegisterForm
from dashboards.models import Feedback, Notification, Profile


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

        pending = PendingRegistration.objects.get(username='newuser')
        self.assertRedirects(response, reverse('verify_wait', args=[pending.id]))
        self.assertFalse(User.objects.filter(username='newuser').exists())
        self.assertEqual(pending.email, 'newuser@example.com')
        self.assertTrue(pending.profile_image.name.startswith('profiles/'))

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_verifying_pending_registration_creates_user_and_profile_image(self):
        image = SimpleUploadedFile(
            'avatar.gif',
            (
                b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
                b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00'
                b'\x00\x02\x02D\x01\x00;'
            ),
            content_type='image/gif',
        )

        self.client.post(
            reverse('register'),
            {
                'email': 'verifyme@example.com',
                'username': 'verifyme',
                'first_name': 'Verify',
                'last_name': 'Me',
                'password1': 'ComplexPass123!',
                'password2': 'ComplexPass123!',
                'profile_image': image,
            },
        )

        pending = PendingRegistration.objects.get(username='verifyme')
        response = self.client.get(reverse('verify_email', args=[pending.token]))

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username='verifyme')
        self.assertEqual(user.email, 'verifyme@example.com')
        self.assertTrue(user.is_active)
        self.assertTrue(user.profile.profile_image.name.startswith('profiles/'))

    def test_registration_form_places_email_first_and_focuses_email(self):
        form = RegisterForm()

        self.assertEqual(
            list(form.fields.keys()),
            ['email', 'username', 'first_name', 'last_name', 'profile_image', 'password1', 'password2'],
        )
        self.assertTrue(form.fields['email'].widget.attrs.get('autofocus'))
        self.assertEqual(form.fields['email'].widget.attrs.get('autocomplete'), 'email')
        self.assertEqual(form.fields['username'].widget.attrs.get('autocomplete'), 'username')


class FeedbackTests(TestCase):
    def test_feedback_submission_notifies_managers(self):
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        manager = User.objects.create_user(
            username='manager-feedback',
            password='pass1234',
            email='manager-feedback@example.com',
            is_staff=True,
        )
        manager.groups.add(manager_group)

        response = self.client.post(
            reverse('feedback'),
            {
                'name': 'Guest User',
                'email': '',
                'feedback_type': 'Suggestion',
                'subject': 'Dashboard idea',
                'message': 'Please improve the quick actions.',
                'page_url': '/dashboard/',
            },
        )

        self.assertRedirects(response, reverse('feedback'))
        self.assertTrue(
            Notification.objects.filter(
                user=manager,
                title='New feedback submitted',
                link=reverse('dashboard_feedback'),
            ).exists()
        )

    def test_guest_can_submit_feedback_without_email(self):
        response = self.client.post(
            reverse('feedback'),
            {
                'name': 'Guest User',
                'email': '',
                'feedback_type': 'Suggestion',
                'subject': 'Anonymous note',
                'message': 'Email should be optional here.',
                'page_url': '/some-page/',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        feedback = Feedback.objects.get(subject='Anonymous note')
        self.assertEqual(feedback.email, '')
        self.assertIsNone(feedback.user)

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
        feedback_user = User.objects.create_user(username='feedback-owner', password='pass1234', email='owner@example.com')
        feedback = Feedback.objects.create(
            user=feedback_user,
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
        self.assertTrue(Notification.objects.filter(user=feedback_user, title='Feedback updated').exists())


class DashboardFeatureTests(TestCase):
    @staticmethod
    def _valid_gif(name='test.gif'):
        return SimpleUploadedFile(
            name,
            (
                b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
                b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00'
                b'\x00\x02\x02D\x01\x00;'
            ),
            content_type='image/gif',
        )

    def test_user_can_open_saved_posts_and_notifications_pages(self):
        user = User.objects.create_user(username='dash-user', password='pass1234', email='dash@example.com')
        Notification.objects.create(user=user, title='Welcome', message='Hello there.')
        self.client.force_login(user)

        saved_response = self.client.get(reverse('saved_posts'))
        notification_response = self.client.get(reverse('notifications'))
        settings_response = self.client.get(reverse('settings'))

        self.assertEqual(saved_response.status_code, 200)
        self.assertEqual(notification_response.status_code, 200)
        self.assertEqual(settings_response.status_code, 200)
        self.assertContains(notification_response, 'Welcome')

    def test_settings_page_shows_personal_account_actions(self):
        editor_group, _ = Group.objects.get_or_create(name='Editor')
        user = User.objects.create_user(username='settings-user', password='pass1234', email='settings@example.com')
        user.groups.add(editor_group)
        Notification.objects.create(user=user, title='Theme hint', message='Try dark mode.')

        self.client.force_login(user)
        response = self.client.get(reverse('settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Settings')
        self.assertContains(response, 'Appearance and notifications')
        self.assertContains(response, 'Change password')
        self.assertContains(response, reverse('edit_my_profile'))
        self.assertContains(response, reverse('my_profile'))

    def test_manager_settings_page_shows_staff_controls(self):
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        manager = User.objects.create_user(username='settings-manager', password='pass1234', is_staff=True)
        manager.groups.add(manager_group)

        self.client.force_login(manager)
        response = self.client.get(reverse('settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('dashboard_feedback'))
        self.assertContains(response, reverse('reports'))

    def test_settings_page_can_update_preferences(self):
        user = User.objects.create_user(username='settings-save', password='pass1234', email='save@example.com')
        self.client.force_login(user)

        response = self.client.post(
            reverse('settings'),
            {
                'form_type': 'preferences',
                'theme_preference': 'dark',
                'notify_post_updates': 'on',
                'notify_feedback_updates': 'on',
            },
        )

        self.assertRedirects(response, reverse('settings'))
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.theme_preference, 'dark')
        self.assertFalse(user.profile.notify_new_followers)
        self.assertTrue(user.profile.notify_post_updates)
        self.assertTrue(user.profile.notify_feedback_updates)
        self.assertFalse(user.profile.notify_report_updates)

    def test_settings_page_can_change_password(self):
        user = User.objects.create_user(username='settings-password', password='pass1234', email='password@example.com')
        self.client.force_login(user)

        response = self.client.post(
            reverse('settings'),
            {
                'form_type': 'password',
                'old_password': 'pass1234',
                'new_password1': 'UltraSecurePass987$',
                'new_password2': 'UltraSecurePass987$',
            },
        )

        self.assertRedirects(response, reverse('settings'))
        self.client.logout()
        self.assertTrue(self.client.login(username='settings-password', password='UltraSecurePass987$'))

    def test_profile_page_contains_logout_action(self):
        user = User.objects.create_user(username='profile-logout', password='pass1234', email='profilelogout@example.com')
        self.client.force_login(user)

        response = self.client.get(reverse('my_profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('logout'))
        self.assertContains(response, 'Account Actions')

    def test_disabling_new_follower_notifications_stops_author_alert(self):
        author = User.objects.create_user(username='settings-author', password='pass1234', email='author@example.com')
        follower = User.objects.create_user(username='settings-follower', password='pass1234', email='follower@example.com')
        author.profile.notify_new_followers = False
        author.profile.save(update_fields=['notify_new_followers'])

        self.client.force_login(follower)
        response = self.client.post(reverse('toggle_follow_author', args=[author.username]))

        self.assertRedirects(response, reverse('author_profile', args=[author.username]))
        self.assertFalse(Notification.objects.filter(user=author, title='New follower').exists())

    def test_editor_can_preview_own_draft(self):
        editor_group, _ = Group.objects.get_or_create(name='Editor')
        editor = User.objects.create_user(username='draft-editor', password='pass1234')
        editor.groups.add(editor_group)
        category = Category.objects.create(category_name='Draft Category', owner=editor)
        image = SimpleUploadedFile('draft.jpg', b'filecontent', content_type='image/jpeg')
        post = Blog.objects.create(
            title='Draft Preview Post',
            slug='draft-preview-post',
            category=category,
            author=editor,
            featured_image=image,
            short_description='Draft preview.',
            blog_body='Preview body',
            status='Draft',
            scheduled_for=timezone.now(),
        )

        self.client.force_login(editor)
        response = self.client.get(reverse('preview_post', args=[post.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Preview Mode')

    def test_followers_get_notification_when_author_publishes_post(self):
        editor_group, _ = Group.objects.get_or_create(name='Editor')
        author = User.objects.create_user(username='notify-author', password='pass1234')
        author.groups.add(editor_group)
        follower = User.objects.create_user(
            username='notify-follower',
            password='pass1234',
            email='follow@example.com',
        )
        AuthorFollow.objects.create(follower=follower, author=author)
        category = Category.objects.create(category_name='Notify Category', owner=author)

        self.client.force_login(author)
        response = self.client.post(
            reverse('add_post'),
            {
                'title': 'Fresh Publish',
                'category': category.id,
                'short_description': 'Fresh short description',
                'seo_description': 'Fresh seo description',
                'blog_body': 'This is a published post body.',
                'status': 'Published',
                'is_featured': False,
                'featured_image': self._valid_gif('publish.gif'),
            },
        )

        self.assertRedirects(response, reverse('posts'))
        self.assertTrue(
            Notification.objects.filter(
                user=follower,
                title='New post from notify-author',
            ).exists()
        )

    def test_editor_can_only_view_own_followers(self):
        editor_group, _ = Group.objects.get_or_create(name='Editor')
        editor = User.objects.create_user(username='editor-followed', password='pass1234')
        other_editor = User.objects.create_user(username='other-followed', password='pass1234')
        editor.groups.add(editor_group)
        other_editor.groups.add(editor_group)

        own_follower = User.objects.create_user(username='own-follower', password='pass1234')
        other_follower = User.objects.create_user(username='other-follower', password='pass1234')
        AuthorFollow.objects.create(follower=own_follower, author=editor)
        AuthorFollow.objects.create(follower=other_follower, author=other_editor)

        self.client.force_login(editor)
        response = self.client.get(reverse('followers'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'own-follower')
        self.assertNotContains(response, 'other-follower')
        self.assertEqual(len(response.context['author_sections']), 1)
        self.assertEqual(response.context['author_sections'][0]['author'], editor)

    def test_manager_can_view_all_editor_followers(self):
        editor_group, _ = Group.objects.get_or_create(name='Editor')
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        editor_one = User.objects.create_user(username='editor-one', password='pass1234')
        editor_two = User.objects.create_user(username='editor-two', password='pass1234')
        manager = User.objects.create_user(username='manager-follows', password='pass1234', is_staff=True)
        editor_one.groups.add(editor_group)
        editor_two.groups.add(editor_group)
        manager.groups.add(manager_group)

        follower_one = User.objects.create_user(username='follower-one', password='pass1234')
        follower_two = User.objects.create_user(username='follower-two', password='pass1234')
        AuthorFollow.objects.create(follower=follower_one, author=editor_one)
        AuthorFollow.objects.create(follower=follower_two, author=editor_two)

        self.client.force_login(manager)
        response = self.client.get(reverse('followers'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'follower-one')
        self.assertContains(response, 'follower-two')
        self.assertContains(response, 'editor-one')
        self.assertContains(response, 'editor-two')

    def test_reader_cannot_view_followers_dashboard(self):
        reader = User.objects.create_user(username='plain-reader', password='pass1234')

        self.client.force_login(reader)
        response = self.client.get(reverse('followers'))

        self.assertEqual(response.status_code, 403)

    def test_open_notification_redirects_back_when_linked_post_was_deleted(self):
        user = User.objects.create_user(username='notify-user', password='pass1234', email='notify@example.com')
        notification = Notification.objects.create(
            user=user,
            title='Report submitted',
            message='We received your report.',
            link='/blogs/deleted-story/',
        )

        self.client.force_login(user)
        response = self.client.get(reverse('open_notification', args=[notification.id]), follow=True)

        self.assertRedirects(response, reverse('notifications'))
        self.assertContains(response, 'This post was deleted')

    def test_open_new_follower_notification_redirects_to_followers_page(self):
        editor_group, _ = Group.objects.get_or_create(name='Editor')
        editor = User.objects.create_user(username='editor-notify', password='pass1234', email='editor@example.com')
        editor.groups.add(editor_group)
        notification = Notification.objects.create(
            user=editor,
            title='New follower',
            message='reader1 started following your author profile.',
            link='/blogs/authors/editor-notify/',
        )

        self.client.force_login(editor)
        response = self.client.get(reverse('open_notification', args=[notification.id]))

        self.assertRedirects(response, reverse('followers'))

    def test_manager_can_edit_report_status(self):
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        manager = User.objects.create_user(username='report-manager', password='pass1234', is_staff=True)
        manager.groups.add(manager_group)
        reporter = User.objects.create_user(username='reporter', password='pass1234')
        category = Category.objects.create(category_name='Reports Category')
        post = Blog.objects.create(
            title='Reported Post',
            slug='reported-post',
            category=category,
            author=reporter,
            featured_image=self._valid_gif('reported.gif'),
            short_description='Reported short',
            blog_body='Reported body',
            status='Published',
            published_at=timezone.now(),
        )
        report = ContentReport.objects.create(user=reporter, blog=post, reason='Spam', details='Please review.')

        self.client.force_login(manager)
        response = self.client.post(
            reverse('edit_report', args=[report.id]),
            {
                'status': 'Reviewed',
            },
        )

        self.assertRedirects(response, reverse('reports'))
        report.refresh_from_db()
        self.assertEqual(report.status, 'Reviewed')
        self.assertEqual(report.reason, 'Spam')
        self.assertEqual(report.details, 'Please review.')

    def test_manager_cannot_delete_report(self):
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        manager = User.objects.create_user(username='delete-report-manager', password='pass1234', is_staff=True)
        manager.groups.add(manager_group)
        reporter = User.objects.create_user(username='delete-reporter', password='pass1234')
        category = Category.objects.create(category_name='Delete Reports Category')
        post = Blog.objects.create(
            title='Delete Report Post',
            slug='delete-report-post',
            category=category,
            author=reporter,
            featured_image=self._valid_gif('delete-report.gif'),
            short_description='Delete report short',
            blog_body='Delete report body',
            status='Published',
            published_at=timezone.now(),
        )
        report = ContentReport.objects.create(user=reporter, blog=post, reason='Abuse')

        self.client.force_login(manager)
        response = self.client.get(reverse('delete_report', args=[report.id]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(ContentReport.objects.filter(pk=report.id).exists())


class AuthRecoveryTests(TestCase):
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_flow_is_available_from_login(self):
        user = User.objects.create_user(username='recover-user', password='pass1234', email='recover@example.com')

        login_response = self.client.get(reverse('login'))
        self.assertEqual(login_response.status_code, 200)
        self.assertContains(login_response, reverse('password_reset'))

        reset_response = self.client.post(
            reverse('password_reset'),
            {'email': user.email},
        )
        self.assertRedirects(reset_response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/password-reset/confirm/', mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_flow_updates_password(self):
        user = User.objects.create_user(
            username='recover-complete',
            password='OldPass123!',
            email='recover-complete@example.com',
        )

        response = self.client.post(
            reverse('password_reset'),
            {'email': user.email},
        )

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)

        reset_link = next(
            line.strip()
            for line in mail.outbox[0].body.splitlines()
            if '/password-reset/confirm/' in line
        )
        confirm_path = urlparse(reset_link).path
        landing_response = self.client.get(confirm_path)
        self.assertEqual(landing_response.status_code, 302)

        confirm_response = self.client.post(
            landing_response['Location'],
            {
                'new_password1': 'BrandNewPass123!',
                'new_password2': 'BrandNewPass123!',
            },
            follow=True,
        )

        self.assertRedirects(confirm_response, reverse('password_reset_complete'))
        user.refresh_from_db()
        self.assertTrue(user.check_password('BrandNewPass123!'))

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_for_pending_registration_sends_verification_email(self):
        self.client.post(
            reverse('register'),
            {
                'email': 'pending-recover@example.com',
                'username': 'pending-recover',
                'first_name': 'Pending',
                'last_name': 'Recover',
                'password1': 'ComplexPass123!',
                'password2': 'ComplexPass123!',
            },
        )
        pending = PendingRegistration.objects.get(username='pending-recover')
        mail.outbox.clear()

        response = self.client.post(
            reverse('password_reset'),
            {'email': pending.email},
        )

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/verify-email/', mail.outbox[0].body)
        self.assertIn(str(pending.token), mail.outbox[0].body)

    def test_first_dashboard_login_shows_welcome_once(self):
        user = User.objects.create_user(username='first-login', password='pass1234', email='first@example.com')

        response = self.client.post(
            reverse('login'),
            {'username': 'first-login', 'password': 'pass1234'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Welcome,')
        self.assertNotContains(response, 'Welcome back,')

        dashboard_response = self.client.get(reverse('dashboard'))
        self.assertContains(dashboard_response, 'Welcome back,')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_pending_registration_shows_unverified_banner_on_login(self):
        self.client.post(
            reverse('register'),
            {
                'email': 'pending@example.com',
                'username': 'pending-user',
                'first_name': 'Pending',
                'last_name': 'User',
                'password1': 'ComplexPass123!',
                'password2': 'ComplexPass123!',
            },
        )

        response = self.client.post(
            reverse('login'),
            {'username': 'pending-user', 'password': 'ComplexPass123!'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your email is not verified yet.')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_verify_wait_resend_button_resends_email_and_returns_to_wait_page(self):
        self.client.post(
            reverse('register'),
            {
                'email': 'resend@example.com',
                'username': 'resend-user',
                'first_name': 'Resend',
                'last_name': 'User',
                'password1': 'ComplexPass123!',
                'password2': 'ComplexPass123!',
            },
        )
        pending = PendingRegistration.objects.get(username='resend-user')
        mail.outbox.clear()

        response = self.client.post(
            reverse('resend_verification'),
            {
                'email': pending.email,
                'user_id': pending.id,
                'return_to': 'verify_wait',
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('verify_wait', args=[pending.id]))
        self.assertContains(
            response,
            'If that email is registered and unverified, we sent a new verification link.',
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(str(pending.token), mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_login_unverified_banner_includes_direct_resend_form(self):
        self.client.post(
            reverse('register'),
            {
                'email': 'banner@example.com',
                'username': 'banner-user',
                'first_name': 'Banner',
                'last_name': 'User',
                'password1': 'ComplexPass123!',
                'password2': 'ComplexPass123!',
            },
        )

        response = self.client.post(
            reverse('login'),
            {'username': 'banner-user', 'password': 'ComplexPass123!'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'action="/resend-verification/"')
        self.assertContains(response, 'name="email" value="banner@example.com"', html=False)
