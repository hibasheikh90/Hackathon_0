# ngrok tip 3: Authentication in 5 seconds

## Metadata
- **From:** ngrok team <team@m.ngrok.com>
- **Date:** 2023-09-01 01:47:32
- **Source:** Gmail IMAP
- **UID:** 42

## Body
Hello there!

👋 It's ngrok again. If you're using ngrok to expose endpoints to the internet, you're going to need to protect them. Now let's look at how to do that with Authentication.

Authentication is vital but hard to get right and impossible to add to some legacy apps. Using ngrok, you can add HTTP Basic Auth in one step:

ngrok http 8000 --basic-auth="thomas:anderson"

That's an okay start but for authentication using Identity, we should consider OAuth 2.0, OpenID Connect, or even SAML. ngrok has them all covered out of the box.

Using ngrok for Authentication
(https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VXkz-B1N4rlWW2LpsmV8VbSHjW8SvcRS52Wpj-N8wLL663pyd0W7Y8-PT6lZ3pLN66xwWWyg92GW86MTv-94rBHSW6mNHQt3y9lFDW4Syc036V8S8KW5fZsHl8sSzFrN6pnRcrWx8C6W78DZzp4jF3FGW3vj73z245X0vW8xHgC386qP-MVmB9Z_3bpSbQW2VtKB69khfxDW8D8WYF95GCLVW9csnN13hFCBCW4yW4qL4qfGnvW1chwPh8rvDYTW6X6GdF3ysN7KW9by2P54lkq7BW3_9Djn1TKbBlN6P98NS4vqrWW67w-1m29GJtRW3kvkv683BnvBW90VMSs4w14YSW8wvlJ665yvrmW7BQ0Db33Sm_dW5lM5l52XpwZXVYLTTL39lNT8f6D-L7v04 )

Next up, we'll talk about improving your deployment process with ngrok.

And we'd love to know what you're working on and how we can make ngrok better. If you have 3.14 minutes, please fill our our ngrok user survey (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VXkz-B1N4rlWW2LpsmV8VbSHjW8SvcRS52Wpj-N8wLL4F5n4LbW50kH_H6lZ3pFW6M7sqt7T_RcCW3wDl_y6cq_RVW6Sn2rf6CF7-3W7PxGy62fwHSfW10PRzb7pVW0NVnS0-M93QpWQN2SJZB8Q-xh_VPNlJx3k0BR_W8kMB7f5Rb3ggW83Xv158t-2cgW8sPT6s94_PL7N2Gn-5mV_M_4W8t59271vw6R8W6YddQS1jj7GSW7JqVKc62vsV3W7T1Sjd5XJgrvW36ckjm4rBhz-W2rDFLB8ZgGwRW88PSHf7YczwyN7qtKFJDt0FjW3cq5WG78jb4QW2G7vX560hp6TVQHpJF2PCqt5Vdc3x870Qwc5W36NVhB79NYHhW8KFzGW9lV19XW5LYLT24VjhQgW1CX9bW9cn1jqW2HN33C18WvfwW8shy_82Fyl5WVJ1Zst8Bvy8TVnxvDM9dCKRkf6K8Dwb04 ) .

Let us know if you need a hand!

Keith

LinkedIn (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VXkz-B1N4rlWW2LpsmV8VbSHjW8SvcRS52Wpj-N8wLL5R3pyd0W7lCdLW6lZ3lXW72yrc98lRKvVW2W8STv4MpzDWW3y3hvF6kHfzTN5gJ1sW5QY-lW4D6SSm7-DbfdW45S0lv8gJRpjW42w7GQ6CsnCzW18SCww2WppwNW4S0DHb7SF1dlW3JQ6n-8NmQF8VVkl184-50fyW5f9qlZ6x4gL_W2_XzVL5zdQfcW3Rtbpp8WJWqdW6jqrYL4fprbdW5S4c0Z6tdCfPW5bJcq-1JvzFHW7HKpS61QcKb4W4HvgG462j9xnW140lDp8cgLpGN8SD9PGWjFSVW7wvP838MGQlFVqT_205hYyGjVF4Kt11KFhQJdsgDbW04 )

Twitter (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VXkz-B1N4rlWW2LpsmV8VbSHjW8SvcRS52Wpj-N8wLL5R3pyd0W7lCdLW6lZ3nfW4Pz0Ck4vJ-pqVYx_qm4v7_fZW5WL21F3qb8dWW5KXSf02m8hmfW3K_Gsl47VgctW5hMQ5M2VzWk_W5H7B908lXyxDV5CXMq98cm4VW8FwGFy17tvysW6TWB6D5TbR4ZW7hFJPp3V1Qm_W5HVTcB2NDW8cW2NZrds6X6C75VCMYs17dZ-72W4v3WRH3wBhnXW1r-Kq53bFHsYVM_gWY5kKDN9W2zdwJS4kZMYjW4j_m6L4zPrxWW27JqqF3hw-kVVLsKqb4VyWNlW4kJkw52-3mlnW91rY7_2Gb69CVLSN2_7YtnmndT2WQz04 )

Website (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VXkz-B1N4rlWW2LpsmV8VbSHjW8SvcRS52Wpj-N8wLL5x3pyd0W6N1vHY6lZ3mlVQ1vT24_ypyVW5wHNdW1xW5pYW6JzX6C6w6VH0W13YCLx3yvNNBW1MFSzN5tQ7flW91NNDT67LXnLW44nXCy1tRhGtW63K86Z3SzbYDW2TNPzb48TBrZVZ-D0b2DNrr8W3-qkvr50V5nKW89p7G14K0Jf-W62tLP04FPF_KW7l3_dB7K2RRfN4_77BTzn7fjV_bBP2748yl3W27y5X_8PdTkcW5T0M8P80fR_BW4fmJpG5_rZQ2N3Z84XQtVymQW8Xg7PP68qc74W8hgpm-7fHZzgf33fZY004 )

YouTube (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VXkz-B1N4rlWW2LpsmV8VbSHjW8SvcRS52Wpj-N8wLL5R3pyd0W7lCdLW6lZ3nvVfjlRz25HmL2W7yzGdn2sk5NGW7kGy134yV721V8CLMS2FhBK3W26MP857YDDhgW5rz-vP5XgzR-W2chS2j1M4T4TW5DDJx_4JGMRMW9kdwWT6Tdxb6W7BsM0P7LhfHLW4WyjLW2Xc3zLW1S13RW6FVlwDN1brZJLbbwy0W82LSmf32-3WfW3-8cQR42DnZhN5YnDBzsjD4MN8f9wdDpLydDW1fP8Ms67GPhvW2Pg2GM9bb9CxW5RdwXH8NwBLtW3YKtxc6phr8wW4-7RSf2b13KFW26X90R6HHkYKW3hMYXQ8NsvZ2f1Sbxrq04 )

ngrok Inc., 548 Market St, PMB 26741, San Francisco,California,94104-5401,United States,

Unsubscribe (https://hs-21124867.s.hubspotemail.net/hs/manage-preferences/unsubscribe?languagePreference=en&d=Vnd68w6nn5wdVKkYYL1Y_wWhW1X1pYB3_R592N1JxwY5WNDwmN17r7tjQtM9QW6MYmJn6nyZlkVD72F94St0WpW8pQfq88xSXllN5_-1q11yf0NW31yR_72n-2-rW7hC8K7979hb4mgDbTj403&v=3&_hsenc=p2ANqtz-_jnMm6AP5Ib64RXn4i36qIG7th2HpCjpGrT9q3DgLLSleGAlAP7cQrTQMNeR_1NC79GJfXoNYCKm4W-DT_JuOK8Q-Leg&_hsmi=238290841 ) Manage Preferences (https://hs-21124867.s.hubspotemail.net/hs/manage-preferences/unsubscribe?languagePreference=en&d=Vnd68w6nn5wdVKkYYL1Y_wWhW1X1pYB3_R592N1JxwY5WNDwmN17r7tjQtM9QW6MYmJn6nyZlkVD72F94St0WpW8pQfq88xSXllN5_-1q11yf0NW31yR_72n-2-rW7hC8K7979hb4mgDbTj403&v=3&_hsenc=p2ANqtz-_jnMm6AP5Ib64RXn4i36qIG7th2HpCjpGrT9q3DgLLSleGAlAP7cQrTQMNeR_1NC79GJfXoNYCKm4W-DT_JuOK8Q-Leg&_hsmi=238290841 )
