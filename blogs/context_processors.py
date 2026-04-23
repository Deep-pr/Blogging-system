from .models import Category
from about.models import SocialLink

def get_categories(request):
    categories = Category.objects.all()
    return dict(categories=categories)



def get_social_links(request):
    social_links = SocialLink.objects.all()
    return dict(social_links=social_links)


def get_default_seo(request):
    url_name = ''
    if getattr(request, 'resolver_match', None):
        url_name = request.resolver_match.url_name or ''

    default_page_title = 'FutureFlux'
    default_meta_description = 'Stories, ideas and perspectives worth reading.'
    default_noindex = False
    default_canonical_url = request.build_absolute_uri(request.path)
    show_flash_messages = False

    # Utility/auth views should not be indexed.
    utility_pages = {
        'search',
        'feedback',
        'login',
        'register',
        'logout',
        'password_reset',
        'password_reset_done',
        'password_reset_confirm',
        'password_reset_complete',
        'resend_verification',
        'verify_wait',
        'verify_email',
        'check_verification',
        'sitemap_xml',
    }

    # Public pages with better default metadata.
    public_defaults = {
        'home': (
            'FutureFlux | Stories Worth Reading',
            'Discover thoughtful stories, practical ideas, and fresh perspectives across technology, business, design, and culture.',
            False,
        ),
        'search': (
            'Search Articles | FutureFlux',
            'Search articles by keyword, category, author, and date on FutureFlux.',
            True,
        ),
        'feedback': (
            'Send Feedback | FutureFlux',
            'Report bugs, suggestions, and content issues to help improve FutureFlux.',
            True,
        ),
        'login': (
            'Login | FutureFlux',
            'Sign in to manage your profile, posts, notifications, and dashboard settings.',
            True,
        ),
        'register': (
            'Register | FutureFlux',
            'Create your FutureFlux account to follow authors, save posts, and publish stories.',
            True,
        ),
        'password_reset': (
            'Reset Password | FutureFlux',
            'Request a secure password reset link for your FutureFlux account.',
            True,
        ),
        'password_reset_done': (
            'Check Your Email | FutureFlux',
            'If an account exists for that email, a password reset link has been sent.',
            True,
        ),
        'password_reset_confirm': (
            'Set New Password | FutureFlux',
            'Choose a new password for your FutureFlux account.',
            True,
        ),
        'password_reset_complete': (
            'Password Updated | FutureFlux',
            'Your FutureFlux password was updated successfully.',
            True,
        ),
        'resend_verification': (
            'Resend Verification | FutureFlux',
            'Request a new email verification link for your FutureFlux account.',
            True,
        ),
        'verify_wait': (
            'Verify Email | FutureFlux',
            'Complete email verification to activate your FutureFlux account.',
            True,
        ),
        'verify_email': (
            'Email Verification | FutureFlux',
            'Confirm your FutureFlux email address.',
            True,
        ),
        'posts_by_category': (
            'Category Articles | FutureFlux',
            'Explore articles by category on FutureFlux.',
            False,
        ),
        'author_profile': (
            'Author Profile | FutureFlux',
            'Read stories by FutureFlux authors.',
            False,
        ),
        'blogs': (
            'Article | FutureFlux',
            'Read thoughtful articles on FutureFlux.',
            False,
        ),
    }

    if request.path.startswith('/dashboard/'):
        label = (url_name or 'dashboard').replace('_', ' ').title()
        default_page_title = f'{label} | FutureFlux Dashboard'
        default_meta_description = 'Manage your profile, posts, categories, notifications, analytics, feedback, and reports in the FutureFlux dashboard.'
        default_noindex = True
        default_canonical_url = ''
        show_flash_messages = True
    elif url_name in public_defaults:
        title, description, noindex = public_defaults[url_name]
        default_page_title = title
        default_meta_description = description
        default_noindex = noindex
        show_flash_messages = url_name in {
            'feedback',
            'login',
            'register',
            'resend_verification',
            'password_reset',
            'password_reset_done',
            'password_reset_confirm',
            'password_reset_complete',
        }
    elif url_name in utility_pages:
        default_noindex = True
        show_flash_messages = True

    return {
        'default_page_title': default_page_title,
        'default_meta_description': default_meta_description,
        'default_noindex': default_noindex,
        'default_canonical_url': default_canonical_url,
        'show_flash_messages': show_flash_messages,
    }
