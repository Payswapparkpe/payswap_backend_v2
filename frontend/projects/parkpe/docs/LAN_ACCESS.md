# ParkPe – Local network (WiFi/LAN) par access

Phone, tablet ya dusri machine se same WiFi par ParkPe test karne ke liye:

## 1. Apne machine ka LAN IP pata karo

**Mac/Linux:**
```bash
ipconfig getifaddr en0
# ya
hostname -I
```

**Windows:**
```bash
ipconfig
```
`IPv4 Address` dekho (e.g. `192.168.1.5`).

## 2. Backend (Django) – sab interfaces par chalão

Project root (`payswap`) se:
```bash
python manage.py runserver 0.0.0.0:8000
```

API requests Angular proxy se aayenge, isliye `ALLOWED_HOSTS` mein extra add karne ki zaroorat nahi. Agar direct `http://<LAN_IP>:8000` bhi use karna ho to `.env` mein:
```
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.5
```
(apna LAN IP daalo; dev ke liye `*` bhi use kar sakte ho.)

## 3. Frontend (Angular) – LAN par serve karo

`frontend-space/projects/parkpe` se:
```bash
npm run start:lan
```

Ye `ng serve --host 0.0.0.0` chalata hai, isliye app sab network interfaces par available hoti hai (port **4201**).

## 4. Dusri device se open karo

Same WiFi par phone/tablet/laptop se browser mein:
```
http://<LAN_IP>:4201
```
Example: `http://192.168.1.5:4201`

API calls `/api/*` isi URL se jayenge; proxy backend ko `localhost:8000` par forward karega, isliye sab kaam karega.

## Firewall

Agar connect nahi ho raha to Mac/Windows firewall mein port **4201** (aur agar direct API chala rahe ho to **8000**) allow karo.
