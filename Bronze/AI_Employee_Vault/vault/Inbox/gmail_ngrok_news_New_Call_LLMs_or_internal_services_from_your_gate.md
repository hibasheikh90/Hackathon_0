# [ngrok news] New: Call LLMs or internal services from your gateway
 + more production policies to yoink

## Metadata
- **From:** "Joel @ ngrok" <team@m.ngrok.com>
- **Date:** 2025-07-29 15:32:53
- **Source:** Gmail IMAP
- **UID:** 970

## Body
Hi, Muhammad Yasir!

We know you’re busy building, so here’s what’s new from ngrok in July.

We launched the http-request Traffic Policy action (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVw9Rm4f3trgN8WQSpQxcR8TW8mS6hr5zBGnFN5GS5S-3pyd0W8wLKSR6lZ3mKW7l5Hch7gzHXfW8vgdn21dLjmZW1rMGbJ2xQn_7W74xQYV5FkjBZT7YgX97MPcWW82grnv2JZNDjVZJN7R6R6s0FW23mnHd6l8ZFCW8fwz855nDLtRV6nD8c5Ng4-8W7kRLXK90SDPkW4VxmrF628xStN6wzrKDK5LlcW6ZfVJd6VdD1_W4KKKNt6gNP0sW1Bgdz-2w6W-TW8t1Rlq1KjMxhW7lZK986vDK-hW8yrQJF5lYXdtW8H34K75FfNz0W6HyLRV4-qJnyT8L3Q1fZgkcW1JtSjV8NLzZ7N3hs54XKrKgRVjmmSn1tR0lBW64jLT04pf0fKW8RPQ008pmx4DW8GydXD8kDXrdf8mb75q04 ) , which lets you call APIs from your Traffic Policy.

```
on_http_request:
  - actions:
      - type: http-request
        config:
          url: https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVw9Rm4f3trgN8WQSpQxcR8TW8mS6hr5zBGnFN5GS5Sn3pyd0W7lCdLW6lZ3kLW4rmYR34HZjSwW69bXVM6G4Y-JN9jnvxPZcXR0W4G1wn18xSdgwW6GsZYK2qL8Z5W6cMfGM7HzFH4W5bfZLB6Z6RJvW230Ymm2GYLnNW5n03dn6kRXszW3DBn_97F4C8sW289cfn1H_ctbW5z5H3V8gBPNPW5FZk_R3fCrdKW5JG6Kv8m4r53W5WP97y7xCTF5N4mmdNdFCTjPN23w1HrRCmQlW3zlxKv4ppkjcW8X5YL26fXQvjW3bG_mW75RXVvVM_2h872CcMkW63xWJS7YsfCZW6DyLHZ6d2jHQW6xFKSy7C1Mrzf1RFNdH04
          method: POST
          headers:
            content-type: application/json
          body: |
            { "token": "${req.headers[\"authorization\"][0]}" }
          on_error: halt
```

This release also brings fun new examples to the gallery and beyond:

- Video: Call an internal Ollama API (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVw9Rm4f3trgN8WQSpQxcR8TW8mS6hr5zBGnFN5GS5Sn3pyd0W7lCdLW6lZ3lKW8rm93G2p6gJNW6y5VFh2grw2dW73Sby794F85vN6Xb13_9FKlSW4ZdCwh61rlmyW1cqryH6N5bbfW7W0T6j54j02yW8t5FJf3b2rTZW7FxhMx2N_CfSW9lmqBQ1RKgyjW1Rnt5Z6TVN_MW3dWH_x2YqSPMW4kBDJR72jT00W6sJkrx6lGmr0N62Tnjj-PDfBW2rfg_42-YQgnVRPtMb6fJkQGV5-7hX52M__qN16zzw9Dbg4SW794ybw903ktRW6zF9gr1vX9HzW225l323hQDSWW4DfCXP2ghD7jW3cS_2C5G-G0Nf8k8H5l04 )
- Example: Apply rate limits ("pre-tiering") to requests based on identity or CRM data (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVw9Rm4f3trgN8WQSpQxcR8TW8mS6hr5zBGnFN5GS5S-3pyd0W8wLKSR6lZ3mkW2xLYSk28BgC4W1T3wzH778KC4W7Rmzvq65fgJ7W5-gxX51ZRC9zW5qS5pr4W3sjzW7Pns-b6bBmpDW60XzD04VJmPjW1JddTV5vBtysW4DK7rB7Mp2WgW2_92kY4fywcPW8zSYtX6RBYVfN3whp-gX3z7XW7fB6F-8xHFcCN483vcjYl5tdW8FBFkX280fy5W8KX4Ht5QvVw1W2_2zRq6MJc61W80-Z9t30HW09W85_zXt37sPzcW1R93Ll1xC1hCW7lW2-s5NbdD5W1bJ0TX4_C71kW8nB9p57n_-cWVGH1ZY7rYMHMW51jdTr520C_HW5S1MLz6x79pxW243swx3MylXfN7g1J019VHkKf1BJZ6804 )
- Example: Validate requests against an internal identity service (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVw9Rm4f3trgN8WQSpQxcR8TW8mS6hr5zBGnFN5GS5Tg3pyd0W95jsWP6lZ3nGW8xFStz2f_tJSW13Hcr34mcsTRW550tcZ6mv8ZRW2m9MWH2GdDJ_W1bVJHk7Qx-LNVkJhZw4Wq0X3W1pdfcx73C8WJW4dJKdg7VP_SGW18cx3Y4tKB_lW4djwbf3B3xpYW1kw3Xp2W9x8YW8Fqjv58wTQmjW40BXKH6FX458N7vf0pdmdxrCW2r1Ccf8YK9JNW1HnCfQ2cp0KFVyZRJw5xPS2VW5TlVml2SgFmdW3KbCFK90T_vdVrPMYM8D7rZRW6hsKB74hMYtYW7rdmGx2XPc6jW7_SwzR7KtypkW1jNy2154llNYW4Pw3yf6kqhrFW7FCW5d1pP4JLW1Mgd1T5Q8q2ZN3JRKJhJjVTmW72jVT28zmqhtW7LTm8X7G88WYf43qLPM04 )

--

Secrets for Traffic Policy (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVw9Rm4f3trgN8WQSpQxcR8TW8mS6hr5zBGnFN5GS5SH3pyd0W7Y8-PT6lZ3l6W150CsG794nHpW1jyfm032NhYBVvyJ2p6xVl9vVjTvqS46CgV-W4F4f5y8TyYWZW8Nh08c1PvT8NW66KTPx2SkVRwN4bYJsghLPWzVSC6c46JqQN6W8z6ddX72SftFW2BdknN5Mg-RsN6XFdvsz6tPdW5T_szt8G7tm0W3KgM_n8T25kQW15gjZH8z39wdW3NjvRw3hqV2sVLml4m3WcnTqN3ZBkMvdkMj0W3gRbzg8r444SW10q9N95ykL3GN2gdbMpZfN4rW535cGj455-RSW1cdSXM6Gnsl9W98hFBr8ck34RW5NVxdx6Wx6kJN4Zds6hKrkZmf4fM1GP04 ) is launched in developer preview! Store API keys or passwords in encrypted vaults and reuse them securely in all your policies.

```
ngrok api vaults create --name "my-vault"
ngrok api secrets create --name "password" --value "hunter22" \
--vault-id="vault_1234"
```

```
on_http_request:
  - actions:
      - type: basic-auth
        config:
          credentials:
            - "alan:${secrets.get('my-vault', 'password')}"
```

--

We added new gateway examples to our gallery:

- Multiplex to internal services from a single domain (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVw9Rm4f3trgN8WQSpQxcR8TW8mS6hr5zBGnFN5GS5S-3pyd0W8wLKSR6lZ3nkN7SB77k8m6p0N8Nfk69vvTMfW8s5Cjn5BpfhnVr16wy3WcfQZVyySXB6xVH1nW4k-_Xx6rRThgN1Z6C0t9nv8RW5c-Lf65PDCxjW5NsRvn6zqc2XW6z2SYP7cBXN2W1qnb5g9gNhhRW2vp-_C6gjP8JW4g2LN12FwXZ4W3xjdhS9hyR0PVkG8zT7KqnqpW15SvdP38YYZ2N3Y3sw3KG6kJW4V22XR1VkckkW94mc03169nfyW48n9QG5v9Cx2W5XdMWZ45mhKZW4xr8Zk946y6lW2wqbz84h-bslW4KXvlW85XBbnW82tZ5l9jzZDxW4-Dp7p58MW-ZVsj6zf3swytXW78lxhs4VyMQLf5l6BLv04 ) : Route to app.your-company.com, api.your-company.com
- Use one AuthN method OR another (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVw9Rm4f3trgN8WQSpQxcR8TW8mS6hr5zBGnFN5GS5Tg3pyd0W95jsWP6lZ3lNW8cGk8p5-QmrxW4LNgms33CbHdV7rlJ829p5vWN8bZJPZZzQsRVYTFK95FkMXwW160y-z3-njJCW90gnLn7T8D-tW6y73x02t-

... (truncated)
