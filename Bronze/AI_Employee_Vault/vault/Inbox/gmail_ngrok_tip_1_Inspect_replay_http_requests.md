# ngrok tip 1: Inspect & replay http requests

## Metadata
- **From:** ngrok team <team@m.ngrok.com>
- **Date:** 2023-08-31 01:47:30
- **Source:** Gmail IMAP
- **UID:** 41

## Body
Debugging is hard.

Okay, that's not the tip. That's a statement but we know every change, push, and refresh is time-consuming. If you're using webhooks, it's even worse because you have to trigger another request.

The tip is that ngrok has a built in UI to capture, inspect, and replay http requests and you already have it configured.

Try the Request Inspector
(https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVrrRZ43-yRyW7hJsSH5Gg86XW4-ljtc52TfzTN1m0Fsq3pyd0W95jsWP6lZ3kwW4w3SjX7CNhD6W7hKMmP1F0T3CW7yZhFs5TVVq8W4mCrGc7hddHpW7HWNQl4H_1xsW3Wr3nV3PJxrwW3-ljHc3YLmxXW9jjxFQ5rc-zsW4ftwWc98Y6s_W4C72ML2WdK-gW73_wfR3HCdgbW4hVjBZ6FdvFFW76JPBG3sKf5BW2p_Qln31Wf1rW4NRvVL4H9rTtW1pyhQy87w738N1MMpPQQz3P0N2h09hT85jpnW2Z3PVC3JK6BnW15vxW85hqQdLW9kz3Fh6n5NxKW5R0mR-2J21YRW796qD67Y7XsTVBtFC24DHFJPW8Kc0xB4XJlZ8W3P2ynC7MvwFJW8f1Kwp8mrs43W4P1X3h2HyntrN6vRGpqkpX4SW6llRxW1xZZzZf8FgDkq04 )

1. Launch ngrok as normal - ngrok http 3001

2. Load the Web Interface in your browser - https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVrrRZ43-yRyW7hJsSH5Gg86XW4-ljtc52TfzTN1m0Frd3pyd0W6N1vHY6lZ3p4W3YCgql7BcGkwW47fK-z5_vJl5W8GfCFF3bnM4fV1z2Rr4l47nVW48n28q1t_HJ4V22NS-16tPX9W57WWTD8pKL7gW4Pl6lr8F75Z6W6-xsF22243c3W8v4v477lF9XQVBGxvZ2yngPGW5JN6sy25YvtVW1TcGv32x2P6jW469Kkb2Lg2ZfW5wVJTl7Vvm3sW1Z-7wW7RWcP1N6yltgKN-lm5W2rk1NM8_xqNSW4JyrMG79G6LSW3Y6ZX82KJsDTW4sbNKp6y2jmNW2fy4L_1XCQH8f699nSb04

3. Select a request and inspect its contents

4. Click Replay.

5. For bonus points, click Replay with Modifications to modify the request.

No, seriously. That's all it takes. Don't believe us? Here's more detail:

Try the Request Inspector
(https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVrrRZ43-yRyW7hJsSH5Gg86XW4-ljtc52TfzTN1m0Fsq3pyd0W95jsWP6lZ3kwW4w3SjX7CNhD6W7hKMmP1F0T3CW7yZhFs5TVVq8W4mCrGc7hddHpW7HWNQl4H_1xsW3Wr3nV3PJxrwW3-ljHc3YLmxXW9jjxFQ5rc-zsW4ftwWc98Y6s_W4C72ML2WdK-gW73_wfR3HCdgbW4hVjBZ6FdvFFW76JPBG3sKf5BW2p_Qln31Wf1rW4NRvVL4H9rTtW1pyhQy87w738N1MMpPQQz3P0N2h09hT85jpnW2Z3PVC3JK6BnW15vxW85hqQdLW9kz3Fh6n5NxKW5R0mR-2J21YRW796qD67Y7XsTVBtFC24DHFJPW8Kc0xB4XJlZ8W3P2ynC7MvwFJW8f1Kwp8mrs43W4P1X3h2HyntrN6vRGpqkpX4SW6llRxW1xZZzZf8FgDkq04 )

PS - Visit our Slack Community (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVrrRZ43-yRyW7hJsSH5Gg86XW4-ljtc52TfzTN1m0Frd3pyd0W6N1vHY6lZ3mYW1y3pr45QHYJJW3fmyb55V3dLZW4yTKrw5flpX5W9kF4zc2PfJRzW7LGv-l3GDj64N3qm1kjDzJZ-W2xzDzp6LdtH6V7sLTL4HV_wfW91Dn601S5LQMW6xMNx04P9yK7W2gR0yB6kZVLTW3Xt0cy8lkCVxW7ygqVJ5mhfp9W7BvHLD2wTSSXW6sbhSR8DbrMlW2LRg9P9d1drhW7HJJCg3cWqTlVCVddd1Gwd76W8wHM-M8xDrKrW81bjTS69DvgZW1FmnRW387mmvW7zhPT73PpMR0f2NnYLg04 ) to learn more and celebrate your victories with us. And we'd love to know what you're working on and how we can make ngrok better. If you have 3.14 minutes, please fill our our ngrok user survey (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVrrRZ43-yRyW7hJsSH5Gg86XW4-ljtc52TfzTN1m0Fql5n4LbW50kH_H6lZ3n5W3pJR3J7Lrk4CW31YwqK1-W9pFW24H5mH67LXJSW7K5YR58WgsKzW7QfR2Y3w1LjyW29xB0X8Rzm-HW5bPDBc5gMK-2VSZCBM39hC31W80kVBF41PtvrW3f7SZJ8nT0jkW7zkM3d30X35WN1fy6sKnktZyW7-lQR741RrFZW5RkZkx2pbB9YW5JJK2P5L6R96W8MpvZP5NKvWdW6ZJNCX1f9Y2BW7vY7S67f3qdwW8z1yCY5yV-SJW5mQmsZ7rDD7NVYLMRC8XQJtsW1LKCg52q9r-3W5jD63_3QmmstW6tGWSt6L2vnxW8TxfCH733ZBgW8c__XF5bF11HW3x25wt23Yt_dW1PkyWz86Y9TGW5ll6XX3Gx1dKW4WjVcS22ZlYJN8bVy0NNRdHrW3ZCJdM5w0DTSf3Dpdyb04 ) .

LinkedIn (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVrrRZ43-yRyW7hJsSH5Gg86XW4-ljtc52TfzTN1m0Frx3pyd0W7lCdLW6lZ3p-W2JrDBL9dR-KkN6GYbXS4J2mhW4dsPPh8YdLbgW8HXRpQ3QJ-FrW4Rzsxt35lfFfW6G1NVr8y5rnZW3JZs0G28fCHbW7HbgSJ6327-VW9fPM7N32fQzYN3hy5ssGs423W6VnW8m6fy4qGVNjSSC69WmPNW5jM_px3MqR_lN9bnKnYScjFcN2vz-tGB9Fy3W5g44ml9cTy51W1DzH-r2Nd10nW4hsBWY5v_l-sW4djC0R3hrQbfW7mzy1Q1YD-F9W7gB1bY1rdM-hW7XTHq13rp6CpW35bQC_1tZNQ4W2h0Fj22HVtQYdhRwj404 )

Twitter (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVrrRZ43-yRyW7hJsSH5Gg86XW4-ljtc52TfzTN1m0Frx3pyd0W7lCdLW6lZ3n_W8jVdWK8stkYpW7QQ9Mm30YQ1sW6F7CNp548JB7W7CJrfq610h-HW89Njh338mK9TW7PqyYD3yRKtfThrPF6MjpyNW8ZjHDS1VzQ2gVLNg-77WqFYlN5RkCyHK6r0XN1cR_QKr9hX4W6tW_2W2X7N-fW1FFLJv1DDCFxN6zzTVBRMQTPW4g_sLL6_LWwKW1x6ZRv1v0yvwW9hJlt98XZ0cmW1JflQy3hLFSSW94n5ld6C2yDNW9l5qZX997Y9DW55YbQ97qGCy_W1mSPhG1pNzfzW1HhMdl1s2ZNTVYqCBY6x9S3_d4Sv6x04 )

Website (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVrrRZ43-yRyW7hJsSH5Gg86XW4-ljtc52TfzTN1m0Frd3pyd0W6N1vHY6lZ3kTW8CGR-j1kkPQLW8KBfGB2z_hYbN17t1p72HZ2PW49ykVf4SGpWnN76tmG_pt8gGW7yGH2k1LPQzKW5Lrwlr5wxYVzW8G5q5f87XVR6W7VWc2H2MVGx9MfZCqMqX9RmW18bKw04C2Qx7W29LSP4821DF5W1mvw-Z7v063xW80jrCt4VcCzkW8QpghH54BYyTW7bpWjd4cVkqmN92Zzc3203pJN8ngn0ppy5yzW5_Gp8k4DCM6XW1gFbQK7sDGNZW6q1WCc1G-M6ZW8c19Ct5mhRj0f6DWsl404 )

YouTube (https://d2v8tf04.na1.hubspotlinks.com/Ctc/5F+113/d2v8tf04/VVrrRZ43-yRyW7hJsSH5Gg86XW4-ljtc52TfzTN1m0Frx3pyd0W7lCdLW6lZ3lqV20bsT7cmQvpW7bJ9Xs5TRVzZVBBZ1J5SvTD3W7RJKMX5srWX-W17RFRJ8sFb2pW7lYjcT3rvHwSM3cTDLKqRNsW4gL8BT8jrQh7W47N6q549bZWRW94jf2Y7w04QkW18d2jj6T8Jr_W6FlSLw4vfJjyW966Lv92DnQNGW53N71x7D

... (truncated)
