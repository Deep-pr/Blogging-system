from django.contrib.auth.models import Group, User
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.template.defaultfilters import slugify
from pathlib import Path

from about.models import About, SocialLink
from blogs.models import Blog, Category, Comment
from dashboards.models import Feedback, Profile


SMALL_GIF = (
    b"GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
    b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)


class Command(BaseCommand):
    help = "Seed the project with mock data for demo and testing."

    def handle(self, *args, **options):
        self.create_groups()
        users = self.create_users()
        self.create_about_and_social_links()
        categories = self.create_categories(users)
        posts = self.create_posts(users, categories)
        self.create_comments(users, posts)
        self.create_feedback(users)
        self.stdout.write(self.style.SUCCESS("Mock data seeded successfully."))

    def create_groups(self):
        for name in ("Manager", "Editor"):
            Group.objects.get_or_create(name=name)

    def create_users(self):
        manager_group = Group.objects.get(name="Manager")
        editor_group = Group.objects.get(name="Editor")

        user_specs = [
            {
                "username": "admin_demo",
                "email": "admin_demo@example.com",
                "password": "DemoPass123!",
                "first_name": "Admin",
                "last_name": "Demo",
                "is_superuser": True,
                "is_staff": True,
                "bio": "Oversees the editorial team and platform quality.",
                "with_photo": True,
            },
            {
                "username": "manager_demo",
                "email": "manager_demo@example.com",
                "password": "DemoPass123!",
                "first_name": "Mira",
                "last_name": "Manager",
                "is_staff": True,
                "groups": [manager_group],
                "bio": "Reviews submissions, feedback, and publishing flow.",
                "with_photo": True,
            },
            {
                "username": "editor_anna",
                "email": "anna@example.com",
                "password": "DemoPass123!",
                "first_name": "Anna",
                "last_name": "Editor",
                "groups": [editor_group],
                "bio": "Writes long-form stories on technology and culture.",
                "with_photo": True,
            },
            {
                "username": "editor_liam",
                "email": "liam@example.com",
                "password": "DemoPass123!",
                "first_name": "Liam",
                "last_name": "Writer",
                "groups": [editor_group],
                "bio": "Covers startups, product strategy, and creator tools.",
                "with_photo": False,
            },
            {
                "username": "reader_demo",
                "email": "reader_demo@example.com",
                "password": "DemoPass123!",
                "first_name": "Ria",
                "last_name": "Reader",
                "bio": "Regular reader who leaves comments and feedback.",
                "with_photo": False,
            },
        ]

        users = {}
        for spec in user_specs:
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "email": spec["email"],
                    "first_name": spec["first_name"],
                    "last_name": spec["last_name"],
                    "is_staff": spec.get("is_staff", False),
                    "is_superuser": spec.get("is_superuser", False),
                    "is_active": True,
                },
            )
            user.email = spec["email"]
            user.first_name = spec["first_name"]
            user.last_name = spec["last_name"]
            user.is_staff = spec.get("is_staff", False)
            user.is_superuser = spec.get("is_superuser", False)
            user.is_active = True
            user.set_password(spec["password"])
            user.save()

            if spec.get("groups"):
                user.groups.set(spec["groups"])

            profile, _ = Profile.objects.get_or_create(user=user)
            profile.bio = spec["bio"]
            if spec["with_photo"] and not profile.profile_image:
                profile.profile_image.save(
                    f"{user.username}.gif",
                    ContentFile(SMALL_GIF),
                    save=False,
                )
            profile.save()
            users[spec["username"]] = user

        return users

    def create_about_and_social_links(self):
        about, _ = About.objects.get_or_create(
            about_heading="About FutureFlux",
            defaults={
                "about_description": "A modern editorial space for technology, business, culture, and thoughtful internet commentary.",
            },
        )
        about.about_description = "A modern editorial space for technology, business, culture, and thoughtful internet commentary."
        about.save()

        social_links = [
            ("Twitter", "https://twitter.com/futureflux"),
            ("LinkedIn", "https://www.linkedin.com/company/futureflux"),
            ("GitHub", "https://github.com/futureflux"),
        ]
        for platform, link in social_links:
            SocialLink.objects.update_or_create(platform=platform, defaults={"link": link})

    def create_categories(self, users):
        category_specs = [
            ("Technology", users["editor_anna"]),
            ("Startups", users["editor_liam"]),
            ("Design", users["editor_anna"]),
            ("Productivity", users["editor_liam"]),
            ("Culture", users["manager_demo"]),
        ]

        categories = {}
        for name, owner in category_specs:
            category, _ = Category.objects.get_or_create(
                category_name=name,
                defaults={"owner": owner},
            )
            category.owner = owner
            category.save()
            categories[name] = category
        return categories

    def create_posts(self, users, categories):
        post_specs = [
            {
                "title": "How Small Teams Ship Faster With Better Editorial Systems",
                "category": categories["Technology"],
                "author": users["editor_anna"],
                "image_path": "media/uploads/2026/03/17/web_development.jpeg",
                "short_description": "A practical look at how lean teams create publishing momentum without chaos.",
                "blog_body": "Strong editorial systems help small teams move faster by clarifying ownership, reducing context switching, and making review smoother.",
                "status": "Published",
                "is_featured": True,
            },
            {
                "title": "Why Developer Experience Is Now a Product Strategy",
                "category": categories["Technology"],
                "author": users["editor_anna"],
                "image_path": "media/uploads/2026/03/09/tech.jpeg",
                "short_description": "Teams that invest in better internal tooling often ship more confidently and consistently.",
                "blog_body": "Developer experience is no longer a backend concern alone. It directly affects release quality, speed, onboarding, and long-term product reliability.",
                "status": "Published",
                "is_featured": False,
            },
            {
                "title": "The Rise of Quiet Infrastructure in Modern Apps",
                "category": categories["Technology"],
                "author": users["editor_anna"],
                "image_path": "media/uploads/2026/03/17/science_DXqi7Q6.jpeg",
                "short_description": "Reliable systems often succeed by being invisible to end users and boring to maintainers.",
                "blog_body": "The best infrastructure is often the least noticeable. Teams benefit most from systems that are steady, observable, and easy to reason about under pressure.",
                "status": "Published",
                "is_featured": False,
            },
            {
                "title": "What Early Startups Get Wrong About Product Launches",
                "category": categories["Startups"],
                "author": users["editor_liam"],
                "image_path": "media/uploads/2026/03/17/business.jpeg",
                "short_description": "Launching is not just about features. It is about timing, positioning, and audience trust.",
                "blog_body": "Startups often focus too heavily on shipping features and too little on narrative, audience fit, and follow-through after launch day.",
                "status": "Published",
                "is_featured": True,
            },
            {
                "title": "How Founder-Led Content Can Create Real Distribution",
                "category": categories["Startups"],
                "author": users["editor_liam"],
                "image_path": "media/uploads/2026/03/09/business.jpeg",
                "short_description": "Founders who share useful thinking consistently can build trust before the product scales.",
                "blog_body": "Founder-led content works when it is generous, specific, and tied to real operating insight. It should build trust rather than simply chase attention.",
                "status": "Published",
                "is_featured": False,
            },
            {
                "title": "The Metrics That Actually Matter Before Product-Market Fit",
                "category": categories["Startups"],
                "author": users["editor_liam"],
                "image_path": "media/uploads/2026/03/15/business.jpeg",
                "short_description": "Early-stage teams often over-measure the wrong things and miss the signals that show real demand.",
                "blog_body": "Before product-market fit, retention quality, repeat behavior, and qualitative pull often matter more than vanity growth numbers.",
                "status": "Draft",
                "is_featured": False,
            },
            {
                "title": "Designing Dashboards That Feel Calm Under Pressure",
                "category": categories["Design"],
                "author": users["editor_anna"],
                "image_path": "media/uploads/2026/03/17/photo-1498050108023-c5249f4df085.jpeg",
                "short_description": "Why clarity, hierarchy, and action grouping matter more than visual density.",
                "blog_body": "Good dashboards reduce anxiety. They show what matters first, keep actions close to context, and avoid overwhelming people with noise.",
                "status": "Published",
                "is_featured": False,
            },
            {
                "title": "Visual Hierarchy That Helps People Decide Faster",
                "category": categories["Design"],
                "author": users["editor_anna"],
                "image_path": "media/uploads/2026/03/08/Screenshot_2026-03-03_at_11.58.34PM.png",
                "short_description": "Strong visual hierarchy reduces hesitation and makes interfaces feel easier to trust.",
                "blog_body": "Good hierarchy guides the eye with intentional contrast, spacing, and grouping so people can decide without hunting for the next step.",
                "status": "Published",
                "is_featured": False,
            },
            {
                "title": "Why Consistency Matters More Than Decoration in UI Systems",
                "category": categories["Design"],
                "author": users["editor_anna"],
                "image_path": "media/uploads/2026/03/17/IMG_20180512_205658.jpg",
                "short_description": "A cohesive interface usually beats a flashy one when the product is used every day.",
                "blog_body": "Consistency lowers cognitive load. Repeated patterns help users build confidence and reduce the effort required to navigate complex workflows.",
                "status": "Published",
                "is_featured": False,
            },
            {
                "title": "The Real Productivity Stack for Creative Work",
                "category": categories["Productivity"],
                "author": users["editor_liam"],
                "image_path": "media/uploads/2026/03/17/science.jpeg",
                "short_description": "A sustainable setup for writing, planning, and publishing without tool overload.",
                "blog_body": "The best productivity stack is often the simplest one. Clear capture, focused execution, and lightweight review loops beat complicated systems.",
                "status": "Draft",
                "is_featured": False,
            },
            {
                "title": "How Writers Can Build Better Weekly Review Habits",
                "category": categories["Productivity"],
                "author": users["editor_liam"],
                "image_path": "media/uploads/2026/03/17/1699631915819.jpeg",
                "short_description": "A simple weekly review helps writers keep momentum without turning planning into another project.",
                "blog_body": "The best weekly review is lightweight. It should surface what shipped, what stalled, and what deserves attention next without becoming administrative overhead.",
                "status": "Published",
                "is_featured": False,
            },
            {
                "title": "The Best Note-Taking Systems Are Easier Than You Think",
                "category": categories["Productivity"],
                "author": users["editor_liam"],
                "image_path": "media/uploads/2026/03/09/science.jpeg",
                "short_description": "Most people do not need a complicated knowledge system to think better and remember more.",
                "blog_body": "Clear capture, useful naming, and occasional review beat elaborate note architectures for most creative and editorial teams.",
                "status": "Published",
                "is_featured": False,
            },
            {
                "title": "Why Internet Culture Keeps Reshaping Modern Publishing",
                "category": categories["Culture"],
                "author": users["manager_demo"],
                "image_path": "media/uploads/2026/03/17/politics.jpeg",
                "short_description": "The line between publishing, community, and product continues to blur.",
                "blog_body": "Internet culture increasingly shapes what gets published, how stories spread, and what readers expect from digital publications.",
                "status": "Published",
                "is_featured": False,
            },
            {
                "title": "What Makes Online Communities Feel Alive Instead of Noisy",
                "category": categories["Culture"],
                "author": users["manager_demo"],
                "image_path": "media/uploads/2026/03/09/sports.jpeg",
                "short_description": "Healthy communities are shaped as much by tone and moderation as by raw participation.",
                "blog_body": "Communities thrive when they create enough structure to feel safe while leaving enough openness for real personality and contribution to emerge.",
                "status": "Published",
                "is_featured": False,
            },
            {
                "title": "Why Audiences Expect More Personality From Brands Now",
                "category": categories["Culture"],
                "author": users["manager_demo"],
                "image_path": "media/uploads/2026/03/17/health.jpeg",
                "short_description": "People increasingly respond to brands that sound human, clear, and consistent over time.",
                "blog_body": "Brand voice matters more when attention is fragmented. Audiences remember clarity and point of view long after campaign moments fade.",
                "status": "Published",
                "is_featured": False,
            },
        ]

        posts = []
        for index, spec in enumerate(post_specs, start=1):
            post, _ = Blog.objects.get_or_create(
                title=spec["title"],
                defaults={
                    "category": spec["category"],
                    "author": spec["author"],
                    "short_description": spec["short_description"],
                    "blog_body": spec["blog_body"],
                    "status": spec["status"],
                    "is_featured": spec["is_featured"],
                },
            )
            post.category = spec["category"]
            post.author = spec["author"]
            post.short_description = spec["short_description"]
            post.blog_body = spec["blog_body"]
            post.status = spec["status"]
            post.is_featured = spec["is_featured"]
            image_source = Path(spec["image_path"])
            if image_source.exists():
                target_name = f"seeded/{image_source.name}"
                if not post.featured_image or Path(post.featured_image.name).name != image_source.name:
                    with image_source.open("rb") as image_file:
                        post.featured_image.save(target_name, File(image_file), save=False)
            elif not post.featured_image:
                post.featured_image.save(
                    f"mock-post-{index}.gif",
                    ContentFile(SMALL_GIF),
                    save=False,
                )
            post.slug = f"{slugify(spec['title'])}-{post.id or index}"
            post.save()
            posts.append(post)
        return posts

    def create_comments(self, users, posts):
        comment_specs = [
            (users["reader_demo"], posts[0], "This was a really clear breakdown of editorial workflow."),
            (users["manager_demo"], posts[0], "We should probably adopt more of this process internally."),
            (users["editor_anna"], posts[1], "The point about launch narrative is especially true."),
            (users["reader_demo"], posts[2], "Calm dashboards are so underrated."),
        ]

        for user, blog, text in comment_specs:
            Comment.objects.get_or_create(user=user, blog=blog, comment=text)

    def create_feedback(self, users):
        feedback_specs = [
            {
                "user": users["reader_demo"],
                "name": "Ria Reader",
                "email": "reader_demo@example.com",
                "feedback_type": "Suggestion",
                "subject": "Add reading time on posts",
                "message": "A reading time estimate near the title would help readers decide what to open.",
                "page_url": "/",
                "status": "New",
            },
            {
                "user": users["manager_demo"],
                "name": "Mira Manager",
                "email": "manager_demo@example.com",
                "feedback_type": "Bug",
                "subject": "Feedback page spacing on mobile",
                "message": "The feedback cards feel a little tight on narrow screens and could use more breathing room.",
                "page_url": "/dashboard/feedback/",
                "status": "Reviewed",
            },
            {
                "user": None,
                "name": "Guest Visitor",
                "email": "guest@example.com",
                "feedback_type": "Content issue",
                "subject": "Broken social link label",
                "message": "One of the social labels looks mismatched with the destination.",
                "page_url": "/",
                "status": "Resolved",
            },
        ]

        for spec in feedback_specs:
            Feedback.objects.get_or_create(
                subject=spec["subject"],
                defaults=spec,
            )
