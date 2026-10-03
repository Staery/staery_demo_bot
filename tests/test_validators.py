import pytest

from bot.services.validators import (
    ValidationError,
    validate_email,
    validate_message,
    validate_name,
    validate_rating,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Ann", "Ann"),
        ("  Anna   Maria ", "Anna Maria"),
        ("Jean-Luc", "Jean-Luc"),
        ("O'Neil", "O'Neil"),
        ("Антон Сёлкин", "Антон Сёлкин"),
        ("J. R. R. Tolkien", "J. R. R. Tolkien"),
    ],
)
def test_valid_names(raw: str, expected: str) -> None:
    assert validate_name(raw) == expected


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("A", "feedback.err_name_length"),
        ("x" * 65, "feedback.err_name_length"),
        ("R2D2", "feedback.err_name_chars"),
        ("<script>", "feedback.err_name_chars"),
        ("--", "feedback.err_name_chars"),
    ],
)
def test_invalid_names(raw: str, key: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_name(raw)
    assert exc_info.value.key == key


def test_email_domain_is_lowercased() -> None:
    assert validate_email(" Ann.Lee+bot@Example.COM ") == "Ann.Lee+bot@example.com"


@pytest.mark.parametrize("raw", ["", "ann", "ann@", "@example.com", "ann@example", "a b@c.io"])
def test_invalid_emails(raw: str) -> None:
    with pytest.raises(ValidationError):
        validate_email(raw)


@pytest.mark.parametrize(("raw", "expected"), [(1, 1), ("5", 5), (" 3 ", 3), ("⭐⭐⭐⭐", 4)])
def test_valid_ratings(raw: str | int, expected: int) -> None:
    assert validate_rating(raw) == expected


@pytest.mark.parametrize("raw", [0, 6, "0", "10", "five", "", "⭐" * 6])
def test_invalid_ratings(raw: str | int) -> None:
    with pytest.raises(ValidationError):
        validate_rating(raw)


def test_message_length_bounds() -> None:
    assert validate_message("  exactly10!  ") == "exactly10!"
    with pytest.raises(ValidationError) as short:
        validate_message("too short")
    assert short.value.params == {"min": 10}
    with pytest.raises(ValidationError) as long:
        validate_message("x" * 1001)
    assert long.value.key == "feedback.err_message_long"
