import pytest

from jamovi.server import i18n


@pytest.fixture
def catalogues(tmp_path, monkeypatch):
    """A stand-in for /usr/lib/jamovi/i18n/json, with a few languages shipped."""
    for name in ('de', 'fr', 'zh-cn'):
        (tmp_path / f'{ name }.json').write_text('{"locale_data":{"messages":{}}}')
    monkeypatch.setattr(i18n, '_i18n_path', lambda: str(tmp_path))
    i18n.catalogue_for.cache_clear()
    yield
    i18n.catalogue_for.cache_clear()


@pytest.mark.parametrize(
    "header, expected",
    [
        ('en-US', 'en'),                      # the browser that used to 404 on /i18n/en-US.json
        ('en', 'en'),
        ('vi', 'en'),                         # no Vietnamese catalogue: serve the source strings
        ('vi,en-US;q=0.9,en;q=0.8', 'en'),
        ('fr-FR,fr;q=0.9', 'fr'),             # the file name, not the tag the browser sent
        ('zh-CN', 'zh-cn'),
        ('de,fr;q=0.5', 'de'),
        ('hr,de;q=0.9', 'de'),                # first preference with a catalogue wins
        ('', 'en'),
        ('*', 'en'),
        ('nonsense', 'en'),
        ('fr;q=bogus', 'en'),
    ],
)
def test_only_a_language_the_server_can_answer_is_selected(catalogues, header, expected):
    assert i18n.best_language(header) == expected


def test_preferences_are_ordered_by_quality_not_by_header_order(catalogues):
    assert i18n._parse_accept_language('fr;q=0.2, de;q=0.9') == ['de', 'fr']


def test_a_language_set_from_the_settings_is_left_alone(catalogues):
    """The UI can pick a language explicitly; only the header is a guess."""
    assert i18n.catalogue_for('de') == 'de'
    assert i18n.catalogue_for('vi') is None
