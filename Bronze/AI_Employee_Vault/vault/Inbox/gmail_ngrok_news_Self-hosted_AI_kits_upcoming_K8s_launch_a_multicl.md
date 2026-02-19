# [ngrok news] Self-hosted AI kits + upcoming K8s launch + a
 multicloud API gateway that just works

## Metadata
- **From:** "Joel @ ngrok" <team@m.ngrok.com>
- **Date:** 2025-03-26 09:47:35
- **Source:** Gmail IMAP
- **UID:** 622

## Body
Preview new K8s ships, a new self-hosted AI community project, and all the ways to hang with an ngrokker at KubeCon!

View in browser (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VV_9CB6BkHL_Vp6yM05dNnGsW4bWRWk5tDlt1N5ZDtTT5n4LbW7lCGcx6lZ3k_W6GbP4b4m5cfxW4ql9xL8zlLx9W6p6LwK7Q7HY4W1Cjngp12WdCvW4vRgbG60wGg3W1Pf4f625v4XyW9cXcXJ2L4MsJN60vKpQldW72W92MBNL5fC_WcW6l9Djg24m8fJW4pDjGS6bnz4qW91LXB63SsgFQW645sy28Lw7vzW60mFNT9hbt6dVj87zT4Vm2rLW7vb9CG4hJHYkVKN9rg7Tx3qJW35kq0H82Q0hFW1hl0q65HP-XwW3nL5DY43xRvBMfSlHZ7Q4bWW7Csq-j4wPQF1W2qsV322czRYYW8cQzZw4v-rTqW8LfwzR4BDJ6bW8r7jpZ5zDNYrW8sWg1F1ccqmxW44yYN-8d9CBqW8nRmjw2QKJvvW6qdzML3mkJncVxzfXX4_3Jv3N4rb-01tN8LcW20P2w94R7lxcW5TBXPR6HrDDLW2_0m8x6b9zd8W4wzYpC6CwY-JVs4_L87Ms4WZW6_pn9d6G-cGVW1t-VY_5MJHXdW30dqfV8l8Qnvf2-02Ws04 )

---

Hi, Muhammad Yasir! Welcome to the (real) March edition of the ngrok newsletter.

Hosting multiple services (or even replicating one!) across multiple clouds is always going to be tough because networking in different clouds looks and works differently. ngrok makes the networking part of going multicloud really easy. Doesn’t matter if you need active/active, failover readiness, are acquiring a GCP shop when you’re all-in an AWS, or just want to secure some GPUs on the cheap. To explain how that works with minimal setup and firefighting, we’ve enlisted our in-house experts.

First up is Shub Argha, Senior Solutions Architect, with an "unboxing" of ngrok’s entire API gateway. He starts with the fundamentals you need to know like endpoints and Traffic Policy—even if you're not going multicloud yet—and ends up with a network architecture on AWS and Azure that fails over to GCP and leaves traffic management rules, like rate limiting, in place during outages.

Watch Shub’s comprehensive demo video → (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VV_9CB6BkHL_Vp6yM05dNnGsW4bWRWk5tDlt1N5ZDtVM3pyd0W95jsWP6lZ3pNW2Lz22W5skqFhW9kFk2z83wLntW8lFQbS4QH6FXW21SSfJ8G4bspW4gzHzd1vnWngW8G80D-2756SHF14M5y0FtckVH80Fp1tMCYLW1BTbjz6gcTH-V6pQz15Q8mrcN86Tp0zCxf7pW7qk27s9jcMfRW6wDFmn8Pz0MMW8KRxFP8PZYbZW3Rp-lD1yWTdnW7_w12-5VfGyhW4QPfNt3d99JcW4ng2m21GPKrbW3NMCNw8qxCjlW8FtDk_4qR2cQN80wDwm7wd7VV5Kdyq4xLjycW51DdpZ8v7K_8W6jjzWY39l4_CW72qd333wypSNN7HdyDlMDYGnW6gq7pH5MGhq7V5fZXf7kQrnhW7xm-Z_8FY-TsW2lQBSD4TGpHSdDG1WH04 )

Alice Wasko (Senior Software Engineer adept in both API gateways and Kubernetes Gateway API!) to detail the complexities of multicloud and what you get when you choose the right cloud-agnostic API gateway.

Check it out on YouTube → (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VV_9CB6BkHL_Vp6yM05dNnGsW4bWRWk5tDlt1N5ZDtTT3pyd0W7lCdLW6lZ3mHW6VQGfg1Mm-NCW7jF0Ff4s3n7DW8XsW7f2Xhhs6W7vS9BR4jRYyyW97d86t7h9DcBW6vgdS73r5jTXN6rWbgD_9kNvW4-QHxV1cpLd_W4N9cR04j5Y8JW3zjfZP759M-8W4JswlT1pfhRRW8T7cC55ndVcNW5wqH5Y57_z7qW6cMWGP588BGyN7hJ0FBWp0-6W5-CYFt1tJ3JdW5nMkRQ3LHRttW5Zj8B221SzHgW8l9pwf5KM8_BN2qvPMqRVhz4W8Kj3hY2R2nk3W61BLPk73xcxBW5Ps18h8PgP_hW6m4Hgh2H5C1df7CQSHR04 )

Or, if you’re ready to play around with ngrok’s multicloud API gateway and our K8s Operator…

We have an end-to-end guide for that → (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VV_9CB6BkHL_Vp6yM05dNnGsW4bWRWk5tDlt1N5ZDtVM3pyd0W95jsWP6lZ3lCW4Tw87y4M-3V3V6Ld1t3VQKXVW2wZk8l2bcbJyW5RQGBl8drYY3W1f0rYC6-prqdN8Z6vb5clkCxW1pTGYL134415W1rXNZN7HH2vgW5K9QnT1lQ3_6W7kwTTg4b0qxVW1xrhfT7gpWhkW8ZGcNx6k5xTrW16FN5s20lmXDW6mrVbJ6NyPPXW8v59xJ1py8wmV9z4FY2CRL1MVDdmnp21SJQVN1Zjz2ZPJw1rMhq5WCLz0NHN5mqkW7LX0FsW8K_bjT4Vv9Z1Vg4_286dNjtPW2_RLBS9kCN3vW7VLhxJ5Q6XkbW1dc89R83kw_vW2Cqhqp4Hx2BjW6fqPz57qC7J2W7CXZqK6StNVFW4L6_pL3fmxzLW8TLkGy44qRM_f7tRVtg04 )

Just want an introduction to the pains of multicloud and how to break free?

Read about the 4 ways multicloud breaks your brain → (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VV_9CB6BkHL_Vp6yM05dNnGsW4bWRWk5tDlt1N5ZDtVs3pyd0W8wLKSR6lZ3mWW5Mhhs33-zhdYW675Lw75sBct5W9bSbpt3TqXfRW32BSnY5vRMNQW3yHQCB2VwL48W6wBWjs1ZGxhqW6tMLCY2jy9GKW7fwk7F3h58_YW6cS09_8_h-t3W23f75Z1ZQ5w_W81cJhR283NWjW92VgB041gGCgW7sjbRV33pdl0W6JRfB_1Qnt-nW8vthhH2dzBM3W7q-zpQ8fbkThW5vzPN65Y_ZjZW3Z8HnY35NvC_W6f12sZ8j7HcWW53sT1x75tWSMW2K2-641-DG_cW3_rH8l5Gx_7wW48lCTt2g9qR3F6KqJ4-VDdHW15DJMY3gGF-pN5525JBCXk0wW6yBFSr6NHHbwW738vKZ73bN2nf2srHpv04 )

## Catch us at KubeCon EU!

A friendly reminder that a solid 14% of ngrok will be in London next week—say hi at our booth, catch a demo of v0.18.0 of the ngrok Kubernetes Operator (including revamped docs and support for TCPRoute and TLSRoute and some product launches we're excited about), ask a question during one of our talks, or grab a drink with us after the showcase closes.

Read our tell-all on where we’ll be and when → (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VV_9CB6BkHL_Vp6yM05dNnGsW4bWRWk5tDlt1N5ZDtVs3pyd0W8wLKSR6lZ3nhN3HTWFqd5lrvW3bmkpw8CnW0hW1_z12H5trdG2W1VmVS982vBR3W406GlV1KchyRW2q0cXQ4jcp55N8cJNGhXRq4CW5XfQxP7bQcqPV5WVGW6lWXrfW12cGxg4NFQdnW2t3T3x84t344W1H_Rmh84tTHvW12LPXL3j

... (truncated)
