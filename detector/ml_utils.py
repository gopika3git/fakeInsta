"""
ML utility for Instagram Fake Profile Detection.
Wraps both prediction modes used by the project:
  1. Manual form (raw 11 features) -> predict_from_form()
  2. Instagram username via Apify -> predict_from_username()
"""
import os
import re
import pickle
import pandas as pd
import numpy as np
from django.conf import settings

FEATURE_ORDER = [
    'profile_pic', 'nums_length_username', 'fullname_words', 'nums_length_fullname',
    'name_equals_username', 'description_length', 'external_url', 'private',
    'posts', 'followers', 'follows',
    'follower_following_ratio', 'suspicious_ratio', 'has_followers', 'has_following',
    'has_posts', 'engagement_score', 'profile_completeness', 'username_quality',
    'has_description'
]

_model = None
_scaler = None


def _load():
    global _model, _scaler
    if _model is None or _scaler is None:
        with open(settings.ML_MODEL_PATH, 'rb') as f:
            _model = pickle.load(f)
        with open(settings.SCALER_PATH, 'rb') as f:
            _scaler = pickle.load(f)
    return _model, _scaler


def _engineer(base):
    """Apply same feature engineering used during training."""
    f = dict(base)
    followers = f['followers']
    follows = f['follows']
    posts = f['posts']

    ratio = follows / followers if followers > 0 else 100
    ratio = min(ratio, 100)
    f['follower_following_ratio'] = ratio
    f['suspicious_ratio'] = 1 if (ratio > 10 or ratio < 0.01) else 0
    f['has_followers'] = 1 if followers > 0 else 0
    f['has_following'] = 1 if follows > 0 else 0
    f['has_posts'] = 1 if posts > 0 else 0
    f['engagement_score'] = posts / followers if followers > 0 else 0
    f['profile_completeness'] = (
        f['profile_pic'] +
        (1 if f['description_length'] > 0 else 0) +
        f['external_url'] +
        (1 if f['fullname_words'] > 0 else 0)
    ) / 4.0
    f['username_quality'] = 1 - f['nums_length_username']
    f['has_description'] = 1 if f['description_length'] > 0 else 0
    return f


def _predict(feature_dict):
    model, scaler = _load()
    df = pd.DataFrame([feature_dict])[FEATURE_ORDER]
    df = df.replace([np.inf, -np.inf], 100).fillna(0) #if not replaced by 100 then fillna(0)
    X = scaler.transform(df)
    pred = int(model.predict(X)[0])
    prob_fake = float(model.predict_proba(X)[0][1])
    verdict = 'FAKE' if pred == 1 else 'REAL'
    return verdict, prob_fake, feature_dict


def predict_from_form(form_data):
    """
    Predict from manually-entered raw 11 features (matches prediction (4).py).
    form_data is a dict with these keys (ints/floats):
      profile_pic, nums_length_username, fullname_words, nums_length_fullname,
      name_equals_username, description_length, external_url, private,
      posts, followers, follows
    """
    base = {
        'profile_pic': int(form_data['profile_pic']),
        'nums_length_username': float(form_data['nums_length_username']),
        'fullname_words': int(form_data['fullname_words']),
        'nums_length_fullname': float(form_data['nums_length_fullname']),
        'name_equals_username': int(form_data['name_equals_username']),
        'description_length': int(form_data['description_length']),
        'external_url': int(form_data['external_url']),
        'private': int(form_data['private']),
        'posts': int(form_data['posts']),
        'followers': int(form_data['followers']),
        'follows': int(form_data['follows']),
    }
    full = _engineer(base)
    return _predict(full)


def _ratio_digits(text):
    if not text:
        return 0.0
    digits = len(re.findall(r'\d', text))
    return digits / len(text) if len(text) > 0 else 0.0


def predict_from_username(username):
    """
    Predict by fetching profile via Apify (matches prediction_realtime.py).
    Returns (verdict, prob_fake, features) on success.
    Raises Exception with friendly message on failure.
    """
    try:
        from apify_client import ApifyClient
    except ImportError:
        raise Exception("apify-client not installed. Run: pip install apify-client")

    client = ApifyClient(settings.APIFY_TOKEN)
    username = username.strip().lstrip('@')

    run_input = {"usernames": [username], "resultsLimit": 1}

    try:
        run = client.actor("apify/instagram-profile-scraper").call(run_input=run_input)
        items = client.dataset(run["defaultDatasetId"]).list_items().items
    except Exception as e:
        raise Exception(f"Apify API error: {str(e)}")

    if not items:
        raise Exception(f"Profile @{username} not found or could not be fetched.")

    user = items[0]
    full_name = user.get('fullName', '') or ''
    biography = user.get('biography', '') or ''
    has_pic = bool(user.get('profilePicUrl'))

    base = {
        'profile_pic': 1 if has_pic else 0,
        'nums_length_username': _ratio_digits(username),
        'fullname_words': len(full_name.split()) if full_name else 0,
        'nums_length_fullname': _ratio_digits(full_name),
        'name_equals_username': 1 if full_name.lower().replace(" ", "") == username.lower() else 0,
        'description_length': len(biography),
        'external_url': 1 if user.get('externalUrl') else 0,
        'private': 1 if user.get('isPrivate') else 0,
        'posts': int(user.get('postsCount') or 0),
        'followers': int(user.get('followersCount') or 0),
        'follows': int(user.get('followsCount') or 0),
    }
    full = _engineer(base)
    verdict, prob, feats = _predict(full)

    # Attach extra metadata for display (named 'meta' not '_meta' — Django templates
    # forbid attribute access on names starting with underscore)
    feats['meta'] = {
        'username': username,
        'full_name': full_name,
        'biography': biography,
        'profile_pic_url': user.get('profilePicUrl'),
        'is_private': user.get('isPrivate', False),
        'is_verified': user.get('verified', False),
    }
    return verdict, prob, feats
