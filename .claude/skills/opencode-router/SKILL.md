# OpenCode Multi-Model Router

## Kiedy używać
Użyj tego skilla dla: generowania testów jednostkowych, eksploracji
nieznanego kodu, sanity-checków wzorów/logiki, masowego refaktoringu,
drugiej opinii o rozwiązaniu. NIE używaj do: architektury, krytycznych
decyzji projektowych, finalnego code review.

## Jak wywołać
npx opencode-ai run -m openrouter/stealth/ox-alpha "TREŚĆ_ZADANIA" --format default

## Autoryzacja
Klucz czytany ze zmiennej środowiskowej $OPENROUTER_API_KEY.
Nigdy nie osadzaj klucza w tym pliku.
