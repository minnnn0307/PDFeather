"""Single source of application identity and release version."""
NAME='PDFeather'
VERSION='1.6.0'
PUBLISHER_KO='조민혁'
PUBLISHER_EN='Minhyeok Cho'
REPOSITORY='minnnn0307/PDFeather'
RELEASES_URL=f'https://github.com/{REPOSITORY}/releases'


def publisher_for_language(language):
    return PUBLISHER_KO if language.lower().replace('_','-').startswith('ko') else PUBLISHER_EN
