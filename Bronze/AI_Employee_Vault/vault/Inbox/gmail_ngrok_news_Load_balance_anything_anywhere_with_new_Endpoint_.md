# [ngrok news] Load balance anything, anywhere with new Endpoint
 Pools

## Metadata
- **From:** "Joel @ ngrok" <team@m.ngrok.com>
- **Date:** 2025-05-21 12:39:28
- **Source:** Gmail IMAP
- **UID:** 775

## Body
Hi, Muhammad Yasir!

Endpoint Pools are here! And it's the most dead-simple load balancer you'll ever use. When you put two or more endpoints on same URL, ngrok load-balances between them whether they're running on different machines, environments, networks, or even in different clouds:

```
ngrok http 8080 --url https://⁠api.⁠example.⁠com --pooling-enabled

# on another machine
ngrok http 8080 --url https://⁠api.⁠example.⁠com --pooling-enabled
```

Read about our Endpoint Pools launch →  (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVVTlJ4bY6sjW7b422k42-s6mW7Y8zfc5wSr6dN5wYXQs5n4LbW50kH_H6lZ3kKW6JVd4B1JvYhRV1-QSZ3c9ssTW66mnXb5sxDdNW6H_l6q5ncLrFW3z3XgX44kqDSW53XPxG98Sl_NW7HhH0g1cd0PrW7_y8YF1CMx3kN4XP5BL6qzKVW7FgMF779Chy1W11dF3S4wGMRxW6bfXXR73VfG3W7rnBB62XgGFkW8lpwJ02f3fDCW4nHlK67MTVgLW2np2FJ4k9Y7gW3vvlmd8QxwQ2W9bFQDZ48XGj4W3p91LY2TKQJWN1TxdLLl95-mW5FQj9J44-3HHW5YftDK5KWqRTW2Zfswx6Vr9QfW7P_l-75BFRrqN2j94dKFtZmxW94CwWT3hBGPgW10XZ3M4-_qMRW8hp-DG2qM4YdN9dgZVCj23NvW7tPrx-6Z7t-6W2756Sn2rf6s9N1gQ10s_rNB1f1TNmMd04 )

I've also published a trio of how-tos based on how you deploy services:

- Load Balancing Between Clouds (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVVTlJ4bY6sjW7b422k42-s6mW7Y8zfc5wSr6dN5wYXQs5n4LbW50kH_H6lZ3pHW27Tw6686501rW1L_Rkf7R9nWpW86Psb4850QvXN3d7FxdmGljgW6l7-MY8xYJLzW4xvMfj8Srg9ZW5pghkb6Cl9MYW8P5v4g5P8jzkW2rcSDf3FBKHTN6pGq0pX5xYcW7skdJz3RFsR-W3N77mq1NVP9yW2J557l4qhMmqW3v6Bc25qCBLCW2DCDYb5vBzlSW5Z39j44pbY6kW5Nrh5B2lqHBCW4ZjpdB24rm4zW4CdMgJ2pgfsKVWjBD871jMxKW29jRc03C9BHzW5wjN5H5Fy5c0V9RFn94B5ztGW1bDzjb3ynN3SW8q3Fj56dQRjMW1h8Vp06mWLd5W3fXMFh8NCQzWW8p1pkY3GY7DGN665wDkr1nL5W87w34p18h4vxW6N4H_X3np-yKM7xdj6W9579f4C0HXv04 )
- Load Balancing Between Services Deployed in Kubernetes (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVVTlJ4bY6sjW7b422k42-s6mW7Y8zfc5wSr6dN5wYXQs5n4LbW50kH_H6lZ3kHW72j0DL37wYzbW6pcgh_3DlmZ7W3DnNRf5S4CXCV72_H-76Lk2XW60cT597XwwhtN9fFtWs-m-shW2SClbV8c48khW2y3McQ5xZrPWW1GTzzD37kXpVW1cMQm87lNL4cV3cKvs5DV6C9W4nn9Jf4yjScFN1jzxc-3xlzsW3cFsJ42v9gQzW2kNjxk9lsPlZW2wGcr298GClCN8LZV_R2Nr5zW7zhZr05B0_xJW74RVmf51Nv6YW5DKrGz7c851KW2Z7jDj3wRmm5VsxkPX4L1xSZW74dYqZ7N9J2WW8fc8MQ2Yt_PZW7cJj-b45zr8lW15T41N6yDxxRN3JP9bXblFBJN8tpCHypyxy0W6S0R5Y5wS5T5W7kkXbc4z6lKdW5nmdzF6WmFPWW3Jwk2n5JSxhdf4-wtxd04 )
- Load Balancing Between Kubernetes Clusters (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVVTlJ4bY6sjW7b422k42-s6mW7Y8zfc5wSr6dN5wYXQM5n4LbW5BWr2F6lZ3mnW73m7ZD6_tR9WVKpRFd1NVcGrN5Lgh5GXT4C9W4RCgVy2RDTC7W2ydpLQ7GSggjW8DpHGf5hS7BFVYhxZ11qCr_dW4ZTtgx7g6KJBW8_7ZVt4cKxhBW1YYGd077RHhvW2TLn8C7lqYnKW23175w8VykZgMcg21d55v84W3Zj0S62BgmPjW36dbRl55XZfMN738L2dWLdWsVHT-sZ3kh8Q2W84Xlcl2WNqqvW5zgXgV2DxCMgW74BpDg8BSztmW4mJ1lp1yQcVTW1gxX-b32nh_DW6wTGHf4R3NFzW6pZ5Hd82ZPdyW1XdB6-5r81q7N6HWC-dm4jc4W2Yk09L8Wdc9QW44w_vh4K2KdhW45ySdZ3pPCbRN5DWwQlX0LJPVGMzkr8jTrvSVLym9N8tW2pSW8527vJ5rSd7JW47WM0n3wTSl2f2K_3kK04 )

Or, watch my big 'ol face in HD giving you the fundamentals of pooling across VMs and K8s clusters in just under 3 minutes.

- https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVVTlJ4bY6sjW7b422k42-s6mW7Y8zfc5wSr6dN5wYXRF3pyd0W7lCdLW6lZ3mwVxpvT-136sW_N69nWDl5nZvTW3Ly6dc7n_Mf0W7WRJHT3fNKRCMhvRffvMcr9W5dQj131GR9jFVF2rB_6pg77gW1GRGYF9lJ2cFW57964d91jzlmW1TlXp_4PM1y8W60zLVX9m5jDyW5B_JqY4dhQCjW7XWVtZ9d_c9zVJ-t6q1GXPNfW8CwJYP2ZWz4kW3Sd6Wt1dyG4QW7S8wtf1JKDctW1LR2z562KbpRW96YHgK8Kt8_YW8WvNzS5FpSlnW1pn44F8-DVNBW6XQJ7c1K3xF_W4hDs4B1-NNJcW5xq1TK7msWclf6lgYkY04

## Protect endpoints with mTLS and a minute of your time

I'm also happy to announce a long-awaited update to Traffic Policy: the terminate-tls action is live, and lets you bring your own certs, route traffic based on TLS handshake details, and wire up mTLS with an unquestionably simpler process than any other gateway you've ever used.

```
on_tcp_connect:
  - actions:
    - type: terminate-tls
      config:
        mutual_tls_certificate_authorities:
          - |-
          -----BEGIN CERTIFICATE-----
          ... certificate ...
          -----END CERTIFICATE-----
```

Read the launch blog → (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVVTlJ4bY6sjW7b422k42-s6mW7Y8zfc5wSr6dN5wYXSx3pyd0W95jsWP6lZ3nrW57MR-61Nk_JDW5t_zfb1v5R96W2Dtd3_8q--_nW8w1Dc81dqPQZW6w9XNk280FQFW7n49Cg6c2F0lV46THL72fBPBW1RgPTW1L6tk4W2yfnr-4BnLw6N40zQDymjYwKW7JRQVb2Ht3qTMkkfHWb8CM5W4xgh2w72L2_zW87Qpqm7lTF1_N7f-MbxQPMJnW6pGB972RvSdpW55Cw5w6d-5gJW8p7Vf85yL-z7VGclYw5NVTq2W4V87jF3l2j1KW6350ds4gQ9bnW6nr6j-5dTKBkW4M2YCP2SL6TsN8gJ0GsPh2B8W6k4MBS5blyK0W7VR-V76B8G9GW8fGxHq7b5LPcW96Nc8H4sxtq1W23lMyG6RcB0PW1kbBjX5pXh-lf5F9tG204 )

## Reuse your Traffic Policy logic with set-vars

Traffic Policy just got cleaner and more readable. You can now define variables once, then reuse them across multiple actions, which means your rules are less repetitive and easier to manage even when your requirements get messier.

Check out variable examples you can use today → (https://d2v8tf04.na1.hubspotlinks.com/Ct

... (truncated)
