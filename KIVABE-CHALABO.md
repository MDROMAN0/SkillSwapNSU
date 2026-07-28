# SkillSwap NSU — kivabe chalabo (Bangla guide)

CSE311L Database Systems Lab er project. Ei file ta pura setup ta step by step
dewa ache. **5 minute lagbe.**

---

## Ki ki lagbe

| Jinis | Ache ki na check koro | Na thakle |
| ----- | --------------------- | --------- |
| XAMPP | `C:\xampp` folder ta ache? | https://www.apachefriends.org |
| Python 3 | Command Prompt e `python --version` likho | https://www.python.org/downloads/ — install korar somoy **"Add python.exe to PATH"** tick dite bhulba na |

---

## Step 1 — MySQL chalu koro

1. **XAMPP Control Panel** open koro.
2. **MySQL** er pashe **Start** button e click koro. Sobuj hoye gele thik ache.
   (Apache lagbe na — Flask nijei web server, Apache er dorkar nei. Sudhu
   phpMyAdmin diye database dekhte chaile Apache o start korba.)

## Step 2 — Database import koro

Project folder er moddhe **`1-IMPORT-DATABASE.bat`** file ta te **double click** koro.

Eta `database\skillexchange_full.sql` ta MySQL e import kore dibe. Sesh e ei table
gulo dekhabe — ei number gulo mile gele bujhba sob thik ache:

| table | rows |
| ----- | ---- |
| `users` | 50 |
| `skills` | 50 |
| `userskills` | 261 |
| `exchangerequests` | 49 |
| `sessions` | 34 |
| `reviews` | 36 |

> **Hate korte chaile:** http://localhost/phpmyadmin → **Import** tab →
> `database/skillexchange_full.sql` select koro → **Go**.

## Step 3 — Website chalu koro

**`2-RUN-WEBSITE.bat`** e double click koro.

Prothom bar 3 ta Python package install hobe (Flask, mysql-connector-python,
Werkzeug) — 30 second moto lagbe. Tarpor browser e nijei khule jabe:

**http://127.0.0.1:5000**

Server bondho korte oi kalo window te **Ctrl + C** chapo (ba window ta close koro).

## Step 4 — Login koro

| Field | Value |
| ----- | ----- |
| Email | `roman.ahmed01@northsouth.edu` |
| Password | `password123` |

Database er **50 ta student er sobar password `password123`** — je kono account
diye dhukte parba. Sign-in page e **"Fill demo credentials"** button e click korle
nijei bhore jabe.

---

## Class e demo dewar somoy ki ki dekhaba

Protita button e click korle nicher dan kone ekta toast ashe jate **je SQL
statement ta asole run holo** seta lekha thake. Eta stage e dekhale
instructor sathe sathe bujhbe je query gulo real.

| Screen | Ki dekhaba | Kon SQL cholbe |
| ------ | ---------- | -------------- |
| Sign in | Login | `SELECT * FROM users WHERE email = %s` + password hash check |
| Register | Notun account | `INSERT users` + 2 ta `INSERT userskills` — **ek transaction e** |
| Home | "Matches for you" | `userskills` er upor **self-join** — duijon er dorkar mile |
| Find | Filter gulo (skill / category / department / level) | ekta parameterised query, sob filter optional |
| Find → Propose | Request pathano | `INSERT INTO exchangerequests ... 'Pending'` |
| Requests | Accept / Decline / Cancel | `UPDATE exchangerequests SET status = ...` |
| Sessions | Session book | `INSERT INTO sessions ...` |
| Sessions | Ek e slot e abar book koro | **UNIQUE (request_id, session_date, session_time)** atkabe |
| Sessions | Mark completed | `UPDATE sessions SET status='Completed'` |
| Reviews | Rating dao | `INSERT INTO reviews ...` |
| Reviews | Same session e abar review koro | **UNIQUE (session_id, reviewer_id)** atkabe |
| Edit profile | Ek e skill dubar add koro | **UNIQUE (user_id, skill_id, skill_type)** atkabe |
| Admin → Students | Ekta student delete koro | **ON DELETE CASCADE** — tar skill, request, session, review sob mile jabe |
| Admin → Skills | Je skill kono request e ache seta delete koro | **ON DELETE RESTRICT** — MySQL mana kore dibe |

Rating gulo `v_user_ratings` **VIEW** theke ashe, table theke na — normalisation
er 3NF part ta ekhane dekhate parba.

---

## Kichu hole ki korba

**"Could not reach MySQL"**
→ XAMPP e MySQL start kora nei. Control Panel e giye Start chapo.

**"Unknown database 'skillexchange'"**
→ Step 2 ta kora hoy nai. `1-IMPORT-DATABASE.bat` chalao.

**MySQL root er password set kora ache**
→ `config.py` khulo, `DB_PASSWORD` line e tomar password ta boshao:
```python
DB_PASSWORD = os.environ.get('SKILLSWAP_DB_PASSWORD', 'tomar_password')
```

**Port 5000 onno kichu use korche**
→ Command Prompt e project folder e giye:
```
set PORT=5050
python app.py
```
Tarpor http://127.0.0.1:5050 e jao.

**"python is not recognized"**
→ Python install nei, ba PATH e nei. Reinstall koro, prothom screen e
"Add python.exe to PATH" tick dao.

---

## GitHub Pages er version

GitHub Pages sudhu static file serve korte pare, Python chalate pare na. Tai
repo er root er `index.html`, `login.html`, `dashboard.html` ityadi file gulo
holo **static preview** — oigulo `static/js/data.js` (seed.sql er export) theke
data pore, tai online e purota dekha jay kintu kichu save hoy na.

Full working version tai — **XAMPP + Flask** diye, upore step 1-3.
