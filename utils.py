import requests


def get_random_image_url():
    response = requests.get('https://source.unsplash.com/random')
    return response.url
