from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView, ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse
from django.conf import settings
from decouple import config
from .models import Media, Review, MEDIA_TYPE_CHOICES, DIFFICULTY_CHOICES
from .forms import MediaForm, ReviewForm
from main_app.utils import fetch_omdb_data, fetch_game_data
from django.apps import apps

# Landing page view
class Home(LoginView):
    template_name = 'home.html'

# Dashboard view
class DashboardView(TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['recently_added'] = Media.objects.filter(user=user).order_by('-created_at')[:12]
        context['favorites'] = Media.objects.filter(user=user, is_favorite=True)
        return context

# Media Index (List all media)
class MediaListView(ListView):
    model = Media
    template_name = 'media/media_index.html'
    context_object_name = 'media_list'

    def get_queryset(self):
        return Media.objects.filter(user=self.request.user).order_by('title')

# Media Filtered by Type (Movies, TV Shows, Anime, Video Games)
class MediaFilteredListView(ListView):
    model = Media
    template_name = 'media/media_index.html'
    context_object_name = 'media_list'

    def get_queryset(self):
        return Media.objects.filter(
            media_type=self.kwargs['media_type'], 
            user=self.request.user
        ).order_by('title')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['media_type'] = self.kwargs['media_type']
        return context

    def get_success_url(self):
        media_type = self.kwargs.get('media_type')
        if media_type:
            return reverse('media_filtered', kwargs={'media_type': media_type})
        return reverse('media_index')

# Media Filtered by Type and Status
class MediaFilteredStatusView(ListView):
    model = Media
    template_name = 'media/media_index.html'
    context_object_name = 'media_list'

    def get_queryset(self):
        return Media.objects.filter(
            media_type=self.kwargs['media_type'],
            status=self.kwargs['status'],
            user=self.request.user
        ).order_by('title')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['media_type'] = self.kwargs['media_type']
        context['status'] = self.kwargs['status']
        return context

# Add Media
class MediaCreateView(LoginRequiredMixin, CreateView):
    model = Media
    form_class = MediaForm
    template_name = 'media/media_form.html'

    def form_valid(self, form):
        form.instance.user = self.request.user
        media_type = self.kwargs.get('media_type')
        search_title = self.request.POST.get('title')

        if media_type == 'game':
            game_data = fetch_game_data(search_title)
            if game_data and isinstance(game_data, list) and len(game_data) > 0:
                game = game_data[0]
                form.instance.title = game.get('name', 'Unknown Title')
                form.instance.genre = ', '.join(genre['name'] for genre in game.get('genres', [])) or 'Unknown Genre'
                form.instance.description = game.get('summary', 'No description available')
                form.instance.image_url = game.get('cover', {}).get('url', '')
            else:
                form.add_error('title', 'Game not found.')
                return self.form_invalid(form)
        else:
            media_data = fetch_omdb_data(search_title)
            if media_data:
                form.instance.title = media_data.get('title')
                form.instance.genre = media_data.get('genre', '')
                form.instance.description = media_data.get('description', '')
                form.instance.image_url = media_data.get('image_url', '')
            else:
                form.add_error('title', 'Media not found.')
                return self.form_invalid(form)

        form.instance.media_type = media_type

        if not form.instance.title:
            form.add_error('title', 'Unable to fetch media data. Please check the title and try again.')
            return self.form_invalid(form)

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['omdb_api_key'] = settings.OMDB_API_KEY
        context['client_id'] = settings.CLIENT_ID
        context['media_type'] = self.kwargs.get('media_type')
        context['media_type_choices'] = MEDIA_TYPE_CHOICES
        if self.kwargs.get('media_type') == 'game':
            context['DIFFICULTY_CHOICES'] = DIFFICULTY_CHOICES
        return context

    def get_success_url(self):
        return reverse('media_filtered', kwargs={'media_type': self.kwargs.get('media_type')})
    
# Search Games
def search_games(request):
    """
    View to search for games via IGDB.
    """
    game_data = []
    if 'query' in request.GET:
        game_title = request.GET['query']
        game_data = fetch_game_data(game_title)
    
    return render(request, 'search_games.html', {'game_data': game_data})

# Media Update View
class MediaUpdateView(LoginRequiredMixin, UpdateView):
    model = Media
    form_class = MediaForm
    template_name = 'media/media_form.html'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        media_type = self.kwargs.get('media_type', self.object.media_type)
        form = self.get_form()

        if form.is_valid():
            return self.form_valid(form, media_type)
        else:
            return self.form_invalid(form)

    def form_valid(self, form, media_type):
        form.instance.user = self.request.user
        # form.instance.difficulty = form.cleaned_data.get('difficulty')
        search_title = self.request.POST.get('title')

        # Fetch data based on media type
        if media_type == 'game':
            game_data = fetch_game_data(search_title)
            if game_data and isinstance(game_data, list) and len(game_data) > 0:
                game = game_data[0]
                form.instance.title = game.get('name', 'Unknown Title')
                form.instance.genre = ', '.join(genre['name'] for genre in game.get('genres', [])) or 'Unknown Genre'
                form.instance.description = game.get('summary', 'No description available')
                form.instance.image_url = game.get('cover', {}).get('url', '')
            else:
                form.add_error('title', 'Game not found.')
                return self.form_invalid(form)
        else:
            media_data = fetch_omdb_data(search_title)
            if media_data:
                form.instance.title = media_data.get('title')
                form.instance.genre = media_data.get('genre', '')
                form.instance.description = media_data.get('description', '')
                form.instance.image_url = media_data.get('image_url', '')
            else:
                form.add_error('title', 'Media not found.')
                return self.form_invalid(form)

        form.instance.media_type = media_type

        if not form.instance.title:
            form.add_error('title', 'Unable to fetch data. Please check the title and try again.')
            return self.form_invalid(form)

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['media'] = self.object
        context['media_difficulty'] = self.object.get_difficulty_display() 
        context['omdb_api_key'] = settings.OMDB_API_KEY
        context['client_id'] = settings.CLIENT_ID
        context['media_type_choices'] = MEDIA_TYPE_CHOICES
        context['media_type'] = self.object.media_type
        if self.object.media_type == 'game':
            context['DIFFICULTY_CHOICES'] = DIFFICULTY_CHOICES
        return context

    def get_success_url(self):
        return reverse('view_media', kwargs={'pk': self.object.pk})


# Delete Media
class MediaDeleteView(DeleteView):
    model = Media
    template_name = 'media/confirm_delete_media.html'

    def get_success_url(self):
        media_type = self.object.media_type
        if media_type:
            return reverse('media_filtered', kwargs={'media_type': media_type})
        return reverse('media_index')

# View Media Details
class MediaDetailView(DetailView):
    model = Media
    template_name = 'media/media_detail.html'
    context_object_name = 'media'

    def get_object(self, queryset=None):
        # Get the object based on the primary key
        return super().get_object(queryset=queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reviews'] = Review.objects.filter(media=self.object)
        return context


# List Favorites
class FavoritesListView(ListView):
    model = Media
    template_name = 'favorites.html'
    context_object_name = 'favorite_list'

    def get_queryset(self):
        return Media.objects.filter(is_favorite=True)

# Add Review
class ReviewCreateView(CreateView):
    model = Review
    form_class = ReviewForm
    template_name = 'review/review_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['media'] = get_object_or_404(Media, id=self.kwargs['pk'])
        context['review'] = None
        return context
    
    def form_valid(self, form):
        review = form.save(commit=False)
        review.media = get_object_or_404(Media, id=self.kwargs['pk'])
        review.user = self.request.user
        review.save()
        return redirect(reverse('view_media', kwargs={'pk': review.media.pk}))
    
    def get_success_url(self):
        return reverse('media_reviews', kwargs={'pk': self.object.media.pk})

# Edit Review
class ReviewUpdateView(UpdateView):
    model = Review
    form_class = ReviewForm
    template_name = 'review/review_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['media'] = self.object.media 
        context['review'] = self.object  
        return context
    
    def get_success_url(self):
        return reverse('media_reviews', kwargs={'pk': self.object.media.pk})

# Delete Review
class ReviewDeleteView(DeleteView):
    model = Review
    template_name = 'review/confirm_delete_review.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['media'] = self.object.media  # Ensure 'object' is available
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()  # Retrieve the object
        if 'confirm' in request.POST:
            return super().post(request, *args, **kwargs)  # Proceed with deletion
        return redirect(reverse('media_reviews', kwargs={'pk': self.object.media.pk}))  # Redirect if not confirmed

    def get_success_url(self):
        return reverse('media_reviews', kwargs={'pk': self.object.media.pk})
    
# Custom signup view
class SignupView(CreateView):
    form_class = UserCreationForm
    template_name = 'registration/signup.html'
    success_url = reverse_lazy('login')  # Redirect to login page after successful signup

# Custom login view (uses built-in Django LoginView)
class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    
class MediaFormView(View):
    template_name = 'media/media_form.html'

    def fetch_media_data(self, search_title):
        return fetch_omdb_data(search_title)

    def post(self, request, *args, **kwargs):
        search_title = request.POST.get('search_title')
        media_type = request.POST.get('media_type', kwargs.get('media_type', None))
        form = MediaForm(request.POST)

        if search_title:
            media_data = self.fetch_media_data(search_title)

            if media_data:
                form = MediaForm(initial={  # Pre-fill form
                    'title': media_data.get('title', ''),
                    'genre': media_data.get('genre', ''),
                    'description': media_data.get('description', ''),
                    'image_url': media_data.get('image_url', ''),
                    'rating': media_data.get('rating', ''),
                    'status': media_data.get('status', None),
                })
            else:
                return render(request, self.template_name, {
                    'form': form,
                    'error': 'Media not found',
                    'search_title': search_title,
                    'media_type': media_type,
                })
        
        # Validate and save the form
        if form.is_valid():
            form.save()
            return redirect('media_index')

        return render(request, self.template_name, {
            'form': form,
            'media_type': media_type,
        })

    def get(self, request, *args, **kwargs):
        media_type = kwargs.get('media_type', None)
        form = MediaForm()
        return render(request, self.template_name, {
            'form': form,
            'media_type': media_type,
        })

