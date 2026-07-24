# Cloud release setup

Эта схема позволяет запускать проверки и сборки в GitHub. Уже запущенная работа
продолжается, даже если локальный компьютер выключен.

## Что уже автоматизировано

- `Quality checks`: TypeScript, PWA-сборка и проверка синтаксиса Python.
- `Build mobile release`: облачная сборка Android/iOS через Expo EAS.
- `Release PWA`: единая проверенная сборка, затем публикация в preview или production.
- Production отделён GitHub Environment и требует ввод `RELEASE`.

GitHub Actions выполняет предсказуемые команды, но сам по себе не разрабатывает
новые функции. Для автономной разработки репозиторий нужно отдельно подключить к
облачному coding agent.

## Однократная настройка GitHub

### 1. Восстановить вход

```bash
gh auth login
```

### 2. Создать Environments

В GitHub открыть `Settings → Environments` и создать:

- `preview`;
- `production`.

Для `production` включить `Required reviewers`. Тогда ни один production-релиз
не начнётся без ручного подтверждения владельца.

### 3. Добавить Expo secret

В `Settings → Secrets and variables → Actions`:

- `EXPO_TOKEN`: токен Expo с правом запуска EAS Build.

### 4. Добавить секреты для PWA

Лучше хранить отдельные значения внутри каждого Environment:

- `DEPLOY_HOST`;
- `DEPLOY_PORT`, обычно `22`;
- `DEPLOY_USER`;
- `DEPLOY_PATH`, полный путь к каталогу `/pwa` (для preview используйте
  отдельный хост или поддомен с тем же путём `/pwa`);
- `DEPLOY_SSH_KEY`, отдельный deploy-ключ без пароля;
- `DEPLOY_KNOWN_HOSTS`, заранее проверенная строка сервера из `known_hosts`.

В Variables каждого Environment добавить:

- `HEALTHCHECK_URL`, например `https://iq-barakah.ru/pwa/`.

Не используйте основной личный SSH-ключ. Создайте отдельный ключ только для
публикации PWA и ограничьте его права каталогом сайта.

## Как выпускать

### PWA

`Actions → Release PWA → Run workflow`.

Сначала выбрать `preview`. После проверки запустить `production` и ввести
`RELEASE`. GitHub дополнительно запросит подтверждение reviewer.

### Android/iOS

`Actions → Build mobile release → Run workflow`.

- `preview` создаёт тестовую сборку;
- `production` создаёт магазинную сборку;
- `android`, `ios` или `all` выбирает платформу.

Ссылка на EAS Build появится в логе шага. GitHub дождётся завершения сборки в
Expo Cloud и покажет итоговый статус: успешно или ошибка.

## Перенос в другой проект

Скопировать `.github/workflows`, заменить рабочий каталог приложения и настроить
два Environment с теми же именами. Секреты никогда не копировать в YAML или git.
