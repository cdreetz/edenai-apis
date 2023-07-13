import pytest
from edenai_apis.utils.ssml import (
    is_ssml,
    get_index_after_first_speak_tag,
    get_index_before_last_speak_tag,
)

class TestIsSSML:
    @pytest.mark.parametrize('ssml_text', [
        "<speak>hello</speak>",
        "<speak version='1.0'>hello</speak>",
    ])
    def test__is_valid_ssml(self, ssml_text: str):
        assert is_ssml(ssml_text) == True, f"ssml_text `{ssml_text}` is valid ssml_text"

    @pytest.mark.parametrize('ssml_text', [
        "hello",
        "<speak>hello",
        "hello</speak>",
        "<speak>hello</speak><speak>hello</speak>",
        "<speak>hello</speak><speak>hello</speak><speak>hello</speak>",
        "<speak>hello</speak>hello",
        "hello<speak>hello</speak>",
        "<speak version='1.0'>hello</speak dsdcs>",
    ])
    def test__is_invalid_ssml(self, ssml_text: str):
        assert is_ssml(ssml_text) == False, f"ssml_text `{ssml_text}` is not valid ssml_text"


class TestGetIndexAfterFirstSpeakTag:
    @pytest.mark.parametrize('ssml_text, expected', [
        ("<speak>hello</speak>", 7),
        ("<speak version='1.0'>hello</speak>", 21),
    ])
    def test__get_index_after_first_speak_tag(self, ssml_text: str, expected: int):
        assert get_index_after_first_speak_tag(ssml_text) == expected, \
            f"ssml_text `{ssml_text}` should return index {expected} after first <speak> tag"

    @pytest.mark.parametrize('ssml_text', [
        "hello",
        "<speak>hello",
        "hello</speak>",
        "<speak>hello</speak>hello",
        "hello<speak>hello</speak>",
        "<speak>hello</speak><speak>hello</speak>",
        "<speak>hello</speak><speak>hello</speak><speak>hello</speak>",
    ])
    def test__get_index_after_first_speak_tag__invalid_ssml(self, ssml_text: str):
        assert get_index_after_first_speak_tag(ssml_text) == -1, \
            f"ssml_text `{ssml_text}` should return index -1 after first <speak> tag"

class TestGetIndexBeforeLastSpeakTag:
    @pytest.mark.parametrize('ssml_text, expected', [
        ("<speak>hello</speak>", 12),
        ("<speak version='1.0'>hello</speak>", 26),
        ])
    def test__get_index_before_last_speak_tag(self, ssml_text: str, expected: int):
        assert get_index_before_last_speak_tag(ssml_text) == expected, \
            f"ssml_text `{ssml_text}` should return index {expected} before last </speak> tag"

    @pytest.mark.parametrize('ssml_text', [
        "hello",
        "<speak>hello",
        "hello</speak>",
        "<speak>hello</speak>hello",
        "hello<speak>hello</speak>",
        "<speak>hello</speak><speak>hello</speak>",
        "<speak>hello</speak><speak>hello</speak><speak>hello</speak>",

    ])
    def test__get_index_before_last_speak_tag__invalid_ssml(self, ssml_text: str):
        assert get_index_before_last_speak_tag(ssml_text) == -1, \
            f"ssml_text `{ssml_text}` should return index -1 before last </speak> tag"

