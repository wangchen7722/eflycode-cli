import requests

# 请求的目标URL
url = "https://hrsscm.vivo.xyz/employee/bank/getBranch"

# 请求头
headers = {
    "Host": "hrsscm.vivo.xyz",
    "Connection": "keep-alive",
    # "bpmToken": "undefined",
    "sec-ch-ua-platform": "\"Windows\"",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "sec-ch-ua": "\"Not(A:Brand\";v=\"99\", \"Google Chrome\";v=\"133\", \"Chromium\";v=\"133\"",
    "Content-Type": "application/json;charset=UTF-8",
    "sec-ch-ua-mobile": "?0",
    "Origin": "https://hrsscm.vivo.xyz",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Referer": "https://hrsscm.vivo.xyz/",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh,zh-TW;q=0.9,en-US;q=0.8,en;q=0.7,zh-CN;q=0.6",
    # 注意：这里的 Cookie 是敏感信息，仅作示例，建议在实际代码中动态获取
    "Cookie": "hello=!0ES5vosTjWPQhxR2/7PvLXsJmXXDP3kd84aMCFTFMrauv14+i6ZKjo2gGx8jjYIQ1A6AkNwypRIkcFeg7uiHotgVuiFSOevc3vdOXIA=",
    "token": "8HIPi8D4vzqNlo3IakrnG6SSkk3aZi1RySBiIuCJSwVlQDZ9Vx7zZWsV812X71RhlYY+eSVzb8IcvAKjEqAM4w=="
}

# 请求体数据
payload = {
    "bankCode": "308",
    "branchName": "济南天桥"
}

# 发送 POST 请求
response = requests.post(url, headers=headers, json=payload)

# 打印结果
print("状态码:", response.status_code)
try:
    print("响应内容:", response.json())
except Exception:
    print("响应文本:", response.text)
