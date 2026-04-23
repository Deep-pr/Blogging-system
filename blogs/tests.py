from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dashboards.models import Notification

from .models import AuthorFollow, Blog, Bookmark, Category, ContentReport, NewsletterSubscription, PostReaction


class PublicBlogFeaturesTests(TestCase):
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

    def setUp(self):
        self.user = User.objects.create_user(username='reader', password='pass1234', email='reader@example.com')
        self.category = Category.objects.create(category_name='Tech')
        image = self._valid_gif('hero.gif')
        self.blog = Blog.objects.create(
            title='Future of Search',
            slug='future-of-search',
            category=self.category,
            author=self.user,
            featured_image=image,
            short_description='A look at search interfaces.',
            blog_body='word ' * 450,
            status='Published',
            published_at=timezone.now(),
        )

    def test_blog_detail_shows_estimated_read_time(self):
        response = self.client.get(reverse('blogs', args=[self.blog.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'min read')

    def test_estimated_read_time_scales_with_post_length(self):
        self.assertGreaterEqual(self.blog.estimated_read_time, 2)

    def test_bookmark_toggle_creates_bookmark(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('toggle_bookmark', args=[self.blog.slug]))

        self.assertRedirects(response, f'{self.blog.get_absolute_url()}#reader-actions')
        self.assertTrue(Bookmark.objects.filter(user=self.user, blog=self.blog).exists())

    def test_guest_can_toggle_bookmark_in_session(self):
        response = self.client.post(reverse('toggle_bookmark', args=[self.blog.slug]))

        self.assertRedirects(response, f'{self.blog.get_absolute_url()}#reader-actions')
        session = self.client.session
        self.assertIn(self.blog.id, session.get('guest_bookmarks', []))

    def test_reaction_toggle_creates_reaction(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('react_to_post', args=[self.blog.slug, PostReaction.LIKE]))

        self.assertRedirects(response, f'{self.blog.get_absolute_url()}#reader-actions')
        self.assertTrue(PostReaction.objects.filter(user=self.user, blog=self.blog, reaction_type=PostReaction.LIKE).exists())

    def test_guest_can_toggle_reaction_in_session(self):
        response = self.client.post(reverse('react_to_post', args=[self.blog.slug, PostReaction.LIKE]))

        self.assertRedirects(response, f'{self.blog.get_absolute_url()}#reader-actions')
        self.assertTrue(
            PostReaction.objects.filter(
                user__isnull=True,
                guest_token=self.client.session.session_key,
                blog=self.blog,
                reaction_type=PostReaction.LIKE,
            ).exists()
        )

    def test_guest_reaction_counts_publicly_on_post(self):
        self.client.post(reverse('react_to_post', args=[self.blog.slug, PostReaction.LIKE]))
        self.blog.refresh_from_db()

        response = self.client.get(reverse('blogs', args=[self.blog.slug]))

        self.assertContains(response, 'Like · 1')

    def test_homepage_spotlight_uses_most_liked_published_post(self):
        spotlight_candidate = Blog.objects.create(
            title='Most Liked Story',
            slug='most-liked-story',
            category=self.category,
            author=self.user,
            featured_image=self._valid_gif('spotlight.gif'),
            short_description='This one should be in the spotlight.',
            blog_body='word ' * 300,
            status='Published',
            published_at=timezone.now() - timedelta(minutes=1),
        )
        lower_ranked_featured = Blog.objects.create(
            title='Featured But Less Liked',
            slug='featured-but-less-liked',
            category=self.category,
            author=self.user,
            featured_image=self._valid_gif('featured.gif'),
            short_description='Featured but not the most liked.',
            blog_body='word ' * 300,
            status='Published',
            is_featured=True,
            published_at=timezone.now(),
        )
        fan_one = User.objects.create_user(username='fan-one', password='pass1234')
        fan_two = User.objects.create_user(username='fan-two', password='pass1234')
        fan_three = User.objects.create_user(username='fan-three', password='pass1234')

        PostReaction.objects.create(user=fan_one, blog=spotlight_candidate, reaction_type=PostReaction.LIKE)
        PostReaction.objects.create(user=fan_two, blog=spotlight_candidate, reaction_type=PostReaction.LIKE)
        PostReaction.objects.create(user=fan_three, blog=lower_ranked_featured, reaction_type=PostReaction.LIKE)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.context['spotlight_post'], spotlight_candidate)
        self.assertNotIn(spotlight_candidate, list(response.context['posts']))

    def test_search_can_sort_by_popular(self):
        less_viewed = Blog.objects.create(
            title='Less Viewed',
            slug='less-viewed',
            category=self.category,
            author=self.user,
            featured_image=self._valid_gif('less-viewed.gif'),
            short_description='Lower views.',
            blog_body='word ' * 200,
            status='Published',
            published_at=timezone.now() - timedelta(days=1),
            view_count=3,
        )
        more_viewed = Blog.objects.create(
            title='More Viewed',
            slug='more-viewed',
            category=self.category,
            author=self.user,
            featured_image=self._valid_gif('more-viewed.gif'),
            short_description='Higher views.',
            blog_body='word ' * 200,
            status='Published',
            published_at=timezone.now(),
            view_count=25,
        )

        response = self.client.get(reverse('search'), {'sort': 'popular'})

        self.assertEqual(response.status_code, 200)
        blogs = list(response.context['blogs'])
        self.assertLess(blogs.index(more_viewed), blogs.index(less_viewed))

    def test_guest_can_report_post(self):
        response = self.client.post(
            reverse('report_post', args=[self.blog.slug]),
            {'reason': 'Spam', 'details': 'Looks suspicious.'},
        )

        self.assertRedirects(response, f'{self.blog.get_absolute_url()}#reader-actions')
        report = ContentReport.objects.get(blog=self.blog, reason='Spam')
        self.assertIsNone(report.user)

    def test_report_submission_notifies_managers(self):
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        manager = User.objects.create_user(
            username='manager-report',
            password='pass1234',
            email='manager-report@example.com',
            is_staff=True,
        )
        manager.groups.add(manager_group)

        response = self.client.post(
            reverse('report_post', args=[self.blog.slug]),
            {'reason': 'Spam', 'details': 'Needs review.'},
        )

        self.assertRedirects(response, f'{self.blog.get_absolute_url()}#reader-actions')
        self.assertTrue(
            Notification.objects.filter(
                user=manager,
                title='New content report',
                link=reverse('reports'),
            ).exists()
        )

    def test_newsletter_subscription_can_be_created(self):
        response = self.client.post(reverse('newsletter_subscribe'), {'email': 'subscriber@example.com'})

        self.assertRedirects(response, reverse('home'))
        self.assertTrue(NewsletterSubscription.objects.filter(email='subscriber@example.com').exists())

    def test_scheduled_posts_publish_when_due(self):
        follower = User.objects.create_user(username='follower', password='pass1234', email='follower@example.com')
        AuthorFollow.objects.create(follower=follower, author=self.user)
        image = self._valid_gif('scheduled.gif')
        scheduled_post = Blog.objects.create(
            title='Scheduled Story',
            slug='scheduled-story',
            category=self.category,
            author=self.user,
            featured_image=image,
            short_description='Scheduled post.',
            blog_body='Scheduled body',
            status='Draft',
            scheduled_for=timezone.now() - timedelta(minutes=5),
        )

        self.client.get(reverse('home'))
        scheduled_post.refresh_from_db()

        self.assertEqual(scheduled_post.status, 'Published')
        self.assertTrue(Notification.objects.filter(user=self.user, title__icontains='Scheduled Story').exists())
        self.assertTrue(Notification.objects.filter(user=follower, title='New post from reader').exists())

    def test_logged_in_user_can_follow_and_unfollow_author(self):
        author = User.objects.create_user(username='author1', password='pass1234', email='author1@example.com')
        self.client.force_login(self.user)

        follow_response = self.client.post(reverse('toggle_follow_author', args=[author.username]))
        unfollow_response = self.client.post(reverse('toggle_follow_author', args=[author.username]))

        self.assertRedirects(follow_response, reverse('author_profile', args=[author.username]))
        self.assertRedirects(unfollow_response, reverse('author_profile', args=[author.username]))
        self.assertFalse(AuthorFollow.objects.filter(follower=self.user, author=author).exists())

    def test_new_follower_notification_links_to_followers_dashboard(self):
        author = User.objects.create_user(username='author3', password='pass1234', email='author3@example.com')
        self.client.force_login(self.user)

        self.client.post(reverse('toggle_follow_author', args=[author.username]))

        notification = Notification.objects.get(user=author, title='New follower')
        self.assertEqual(notification.link, reverse('followers'))

    def test_author_page_shows_follow_button_for_other_users(self):
        author = User.objects.create_user(username='author2', password='pass1234', email='author2@example.com')
        self.client.force_login(self.user)

        response = self.client.get(reverse('author_profile', args=[author.username]))

        self.assertContains(response, 'Follow')
