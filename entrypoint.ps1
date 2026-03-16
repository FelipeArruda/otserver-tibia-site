$ErrorActionPreference = "Stop"

python manage.py migrate --noinput
python manage.py seed_test_user

if ($args.Count -eq 0) {
    python manage.py runserver 0.0.0.0:8000
    exit $LASTEXITCODE
}

if ($args.Count -eq 1) {
    & $args[0]
    exit $LASTEXITCODE
}

& $args[0] @($args[1..($args.Count - 1)])
exit $LASTEXITCODE
