# API Explorer Log System

API Explorer se bheje gaye requests aur unke responses ek alag log category **api_explorer** mein record hote hain, taaki test calls baaki API traffic se alag dekh sakho.

## Kaise kaam karta hai

1. **Browser se request:** Jab aap `/api-explorer/` se "Send" dabate ho, request ke saath header `X-Api-Explorer: true` bheja jata hai.
2. **Middleware:** `RequestLoggingMiddleware` is header (ya Referer mein `api-explorer`) ko dekhta hai aur `extra_data['source'] = 'api_explorer'` set karta hai.
3. **Category:** `write_logs_task` / `categorize_log` is source ko dekhte hue log ko category **api_explorer** deta hai.
4. **Sync logging:** API Explorer requests ke liye log **sync** likha jata hai (Celery ki zaroorat nahi), isliye turant portal logs mein dikh jata hai.

## Log kahan dekhen

- **Portal:** `/logs/?category=api_explorer`
- **Management command:**  
  `python manage.py test_api_and_check_logs`  
  Ye command kuch API v2 endpoints ko hit karta hai (X-Api-Explorer header ke saath), 4 sec wait karta hai, phir last N minutes ke logs summarize karta hai (errors/warnings + api_explorer count).

## Command options

```bash
# Sirf log report (koi request nahi bhejta)
python manage.py test_api_and_check_logs --skip-requests --minutes 60

# Requests bhejna + log report (default: last 5 min)
python manage.py test_api_and_check_logs

# API key ke saath protected endpoints test
python manage.py test_api_and_check_logs --api-key "psk_live_..."
```

## Model / Category

- **LogEntry** model mein `category` ke choices mein `api_explorer` add hai.
- **Log file:** `PAYSWAP_LOG_DIR/api_explorer/portal_api_explorer_YYYY-MM-DD.log` (agar configured ho).

## Fixes applied

- **testserver in ALLOWED_HOSTS:** Management command Django test client use karta hai; `testserver` ko `ALLOWED_HOSTS` mein add kiya gaya taaki command bina DisallowedHost error ke chale.
- **Sync logging for api_explorer:** Bina Celery ke bhi API Explorer ke logs DB mein aa jayein, isliye api_explorer requests ke liye `write_logs_task` sync call hota hai.
