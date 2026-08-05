# PWA payments

The PWA uses the existing YooKassa merchant and the existing `bot_payments`
table. Prices are calculated by the API; the browser never sends an amount.
The bot payment job remains responsible for marking a payment paid, activating
`participants`, referral Barakah accrual, curator notifications, and sending the
first lesson.

## Required server variables

Set these only on `iq-barakah-pwa-api` in Amvera and mark the credentials as
secrets:

- `YOOKASSA_SHOP_ID` — the same shop id used by `iq-barakah-v2`.
- `YOOKASSA_SECRET_KEY` — the same secret key used by `iq-barakah-v2`.
- `PAYMENT_RETURN_URL` — optional; defaults to
  `https://iq-barakah.ru/pwa/?payment=return`.

Never add these values to Expo public variables, PWA files, GitHub commits, or
screenshots.

## Release check

1. Deploy the API branch and confirm `/health` is healthy.
2. Open PWA Profile → Programs and payment.
3. Confirm that the displayed price matches the bot for the same account.
4. Create one YooKassa test payment; verify that a second tap reuses it.
5. Complete the test payment and wait up to two minutes.
6. Confirm `bot_payments.status=paid`, one participant activation, and the same
   progress in PWA, Android, and Telegram Mini App.
7. Test a canceled payment and confirm that no access is granted.

Do not enable the external YooKassa button in App Store or Google Play builds
until store billing policy review is complete. The current UI renders it only on
the web/PWA platform.
