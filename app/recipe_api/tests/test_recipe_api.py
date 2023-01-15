"""
Test for recipe_api.
"""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from rest_framework.test import APIClient
from rest_framework import status

from recipe_api.models import Recipe, Tag
from recipe_api.serializers import RecipeSerializer, RecipeDetailSerializer

RECIPES_URL = reverse('recipe_api:recipe-list')


def recipes_detail_url(recipe_id):
    """Creates and return recipe details URL."""
    return reverse('recipe_api:recipe-detail', args=[recipe_id])

def create_tag(user, **params):
    payload = {
        'name': 'Tag1'
    }
    payload.update(**params)
    return Tag.objects.create(user=user, **payload)

def create_recipe(user, **params):
    payload = {
        'title': 'Sample title',
        'time_minutes': 4,
        'price': Decimal('1.50'),
        'description': 'Sample description',
        'link': 'https://example.com/recipe.pdf',
        'tags': []
    }
    payload.update(params)
    return Recipe.objects.create(user=user, **payload)


class TestPublicRecipeAPI(TestCase):
    """Test unauthenticated API requests."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is required to call API."""
        res = self.client.get(RECIPES_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class TestPrivateRecipeAPI(TestCase):
    """Test authorized API requests."""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email='user@example.com',
            password='userexample123'
        )
        self.client.force_authenticate(user=self.user)

    def test_retrieve_recipes(self):
        """Test retrieve list of recipes."""
        create_recipe(user=self.user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPES_URL)

        recipes = Recipe.objects.all().order_by('-id')
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_recipe_list_limited_to_user(self):
        """Test list of recipes is limited to authenticated users."""
        other_user = get_user_model().objects.create_user(
            email='other@example.com',
            password='password123'
        )
        create_recipe(user=self.user)
        create_recipe(user=other_user)

        res = self.client.get(RECIPES_URL)

        recipes = Recipe.objects.filter(user=self.user).order_by('-id')
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)
        self.assertEqual(len(res.data), len(serializer.data))

    def test_get_recipe_detail(self):
        """Test get details of recipe."""
        recipe = create_recipe(user=self.user)
        res = self.client.get(recipes_detail_url(recipe.pk))
        serializer = RecipeDetailSerializer(recipe)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_create_recipe_success(self):
        """Create recipe with all parameters successfully."""
        payload = {
            'title': 'Sample title',
            'time_minutes': 3,
            'price': Decimal('1.50'),
            'description': 'Sample description',
            'link': 'https://example.com'
        }
        res = self.client.post(RECIPES_URL, payload)
        exists = Recipe.objects.filter(id=res.data['id']).exists()
        recipe = Recipe.objects.get(id=res.data['id'])
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)
        self.assertTrue(exists)
        self.assertEqual(recipe.user, self.user)

    def test_perform_partial_update_recipe(self):
        """Partial update a recipe."""
        payload = {
            'title': 'New title',
            'time_minutes': 120
        }
        recipe = create_recipe(user=self.user)
        res = self.client.patch(recipes_detail_url(recipe.pk), payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        self.assertEqual(recipe.title, payload['title'])
        self.assertEqual(recipe.time_minutes, payload['time_minutes'])

    def test_perform_fully_update_recipe(self):
        """Fully updated recipe."""
        payload = {
            'title': 'New title',
            'time_minutes': 133,
            'price': Decimal('1.0'),
            'description': 'New description',
            'link': 'https://newlink.com'
        }
        recipe = create_recipe(user=self.user)
        res = self.client.put(recipes_detail_url(recipe.pk), payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)
        self.assertEqual(recipe.user, self.user)

    def test_error_when_try_to_change_user(self):
        """Test try to change recipe user with error."""
        new_user = get_user_model().objects.create_user(email='newuser@example.com', password='password123')
        recipe = create_recipe(user=self.user)
        payload = {
            'user': new_user.pk
        }
        res = self.client.patch(recipes_detail_url(recipe.pk), payload)
        recipe.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.user, self.user)

    def test_delete_recipe(self):
        """Fully delete a recipe success."""
        recipe = create_recipe(user=self.user)
        res = self.client.delete(recipes_detail_url(recipe.pk))
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        recipes = Recipe.objects.filter(id=recipe.pk).exists()
        self.assertFalse(recipes)

    def test_try_to_update_other_user_recipe(self):
        """Test trying to update recipe with other user."""
        payload = {
            'title': 'New title',
            'time_minutes': 120
        }
        new_user = get_user_model().objects.create_user(email='newuser@example.com', password='password123')
        recipe = create_recipe(user=new_user)

        res = self.client.patch(recipes_detail_url(recipe.pk), payload)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        recipe.refresh_from_db()
        self.assertNotEqual(recipe.title, payload['title'])
        self.assertNotEqual(recipe.time_minutes, payload['time_minutes'])

    def test_try_to_delete_other_user_recipe(self):
        """Test trying to delete recipe with other user."""
        new_user = get_user_model().objects.create_user(email='newuser@example.com', password='password123')
        recipe = create_recipe(user=new_user)
        res = self.client.delete(recipes_detail_url(recipe.pk))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        exists = Recipe.objects.filter(id=recipe.pk).exists()
        self.assertTrue(exists)

    def test_create_recipe_with_tags(self):
        """Test create a new recipe with multiples tags."""
        create_tag(user=self.user, name='tag1')
        create_tag(user=self.user, name='tag2')
        payload = {
            'title': 'Sample title',
            'time_minutes': 3,
            'price': Decimal('1.50'),
            'description': 'Sample description',
            'link': 'https://example.com',
            'tags': [1,2]
        }
        res = self.client.post(RECIPES_URL, payload)
        exists = Recipe.objects.filter(id=res.data['id']).exists()
        recipe = Recipe.objects.get(id=res.data['id'])
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        tags = recipe.tags.all()
        self.assertEqual(tags[0].pk, payload['tags'][0])
        self.assertEqual(tags[1].pk, payload['tags'][1])
        payload.pop('tags')
        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)
        self.assertTrue(exists)
        self.assertEqual(recipe.user, self.user)

