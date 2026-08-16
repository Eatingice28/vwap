# VWAP Market Context Agent

A simple web dashboard that shows you where a stock is trading relative to its
intraday VWAP, and whether SPY and QQQ have broken out of their premarket
range. It then describes the overall picture in plain English.

**You do not need to know how to code to set this up.** Follow the steps in
order and it takes about 20 minutes.

---

## What this tool does and does not do

**It does:**

- Show the current price of the stock you are watching
- Work out that stock's intraday VWAP (volume weighted average price)
- Tell you whether the stock is above, below, reclaiming or rejecting VWAP
- Work out the premarket high and low for SPY and QQQ
- Tell you whether SPY and QQQ are above, below or inside that range
- Write a plain-English summary and colour it green, red, yellow or gray
- Refresh itself every 30 to 60 seconds

**It does not, and will never:**

- Place a trade
- Connect to a brokerage account
- Tell you to buy or sell anything
- Predict a price or promise a profit

This is an **educational context tool**. It describes what has already
happened. Everything it says is worded as context, not instruction:
"bullish context", "bearish context", "mixed context", "watch area",
"confirmation needed". What you do with that is entirely your decision, and
nothing here is financial advice.

---

## What you see on screen

| Part of the screen | What it tells you |
| --- | --- |
| Big coloured summary box | The overall context in one paragraph |
| Card 1 | Your stock's price, its VWAP, and its VWAP state |
| Card 2 | SPY's price and where it sits vs its premarket range |
| Card 3 | QQQ's price and where it sits vs its premarket range |
| Detail table | Exact numbers for every level |
| Recent changes | A short log of states that flipped while you watched |
| Chart | Price plotted against VWAP for the session |

**The colours:**

- 🟩 **Green** – bullish context
- 🟥 **Red** – bearish context
- 🟨 **Yellow** – mixed context, caution
- ⬜ **Gray** – neutral, nothing decided yet

---

## Quick start

The fastest path is: **deploy it first in demo mode, then add your API key.**
Demo mode uses built-in sample data, so you can get the website working before
you spend anything or sign up for data.

1. Create a GitHub repository and upload these files (Part 2 below)
2. Deploy on Streamlit Community Cloud (Part 3 below)
3. Add your password to secrets (Part 4 below)
4. Later, add a data API key and switch the sidebar to Live mode (Part 1)

---

## Part 1 – Get a market data API key

Polygon.io renamed itself to **Massive.com** in October 2025. Old links
redirect to the new site, and API keys work on both. If you see either name,
it is the same company.

1. Go to <https://polygon.io> (it will redirect to massive.com)
2. Click **Sign up** and create an account with your email
3. Once you are logged in, open your **Dashboard**
4. Find the section called **API Keys**
5. Copy the long key that is shown there. It looks like a random string of
   letters and numbers
6. Keep it somewhere safe for now. Treat it like a password

### An important note about free data

The free plan gives you about **5 requests per minute**, and the data is
**delayed by 15 minutes or is end-of-day only**. This dashboard makes 3
requests each time it refreshes (your stock, SPY and QQQ).

What that means in practice:

- On the free plan, keep the refresh interval at **45 or 60 seconds**
- On the free plan, prices may be delayed, or the app may show you the
  **last completed session** instead of today. It will tell you clearly at
  the top of the screen when that happens
- If you want live intraday prices, you need a paid stocks plan. Check
  current pricing at <https://massive.com/pricing>

**You can skip this whole section for now.** Demo mode works with no key
at all.

---

## Part 2 – Create your GitHub repository

GitHub is where your code lives. Streamlit reads the code from GitHub and
turns it into a website. You do not need to install anything.

1. Go to <https://github.com> and click **Sign up**. Create a free account
2. Verify your email address when GitHub asks
3. Click the **+** icon in the top right corner, then **New repository**
4. Fill in the form:
   - **Repository name:** `vwap-market-context-agent`
   - **Description:** optional
   - Choose **Public**. (Community Cloud's free tier needs a public repo.
     Your secrets are never stored in the repo, so this is safe as long as
     you never paste your API key into a code file.)
   - Do **not** tick "Add a README file" — you already have one
5. Click **Create repository**
6. On the next page, click the link **uploading an existing file**
7. Drag these items into the upload box:
   - `streamlit_app.py`
   - `requirements.txt`
   - `README.md`
   - `.gitignore`
   - the `vwap_agent` folder
   - the `.streamlit` folder
8. Scroll down and click **Commit changes**

> **If the `.streamlit` folder will not upload:** some browsers hide folders
> starting with a dot. That folder is optional. The app works without it. You
> can also create it manually: click **Add file → Create new file**, type
> `.streamlit/config.toml` as the filename, paste the contents in, and commit.

> **Never upload a file called `.streamlit/secrets.toml`.** That file holds
> your password and API key. The included `.gitignore` blocks it, and you will
> enter those values on Streamlit's website instead.

---

## Part 3 – Deploy on Streamlit Community Cloud

1. Go to <https://share.streamlit.io>
2. Click **Sign in with GitHub** and use the account you just made
3. Approve the permissions GitHub asks for
4. Click **Create app** (or **New app**)
5. Choose **Deploy a public app from GitHub**
6. Fill in the three boxes:
   - **Repository:** `your-username/vwap-market-context-agent`
   - **Branch:** `main`
   - **Main file path:** `streamlit_app.py`
7. Optionally click **Advanced settings** and paste your secrets now
   (see Part 4 for exactly what to paste)
8. Click **Deploy**

The first build takes 2 to 5 minutes while it installs the libraries. When it
finishes you get a web address like:

```
https://vwap-market-context-agent.streamlit.app
```

That link works on your phone, your laptop, or anywhere else. Bookmark it.

> Free Community Cloud apps go to sleep after a few days of no visits. If you
> see a "wake up" button, click it and wait about 30 seconds.

---

## Part 4 – Add your secrets (password and API key)

Secrets are private values that live on Streamlit's servers, never in your
code. This is how you keep your API key out of GitHub.

1. Open your app at <https://share.streamlit.io>
2. Find your app in the list, click the **⋮** menu, then **Settings**
3. Click the **Secrets** tab
4. Paste exactly this, replacing the values in quotes with your own:

```toml
app_password = "pick-a-password-here"
polygon_api_key = "paste-your-api-key-here"
use_massive_host = false
```

5. Click **Save**. The app restarts by itself after a few seconds

**Notes:**

- Keep the quotation marks around the password and the key
- `use_massive_host` has no quotes. Leave it as `false` unless
  `api.polygon.io` ever stops working, then set it to `true`
- You can add only `app_password` at first and add the key later
- If you set no password at all, the app warns you that anyone with the
  link can open it

### Running it on your own computer instead (optional)

If you would rather test locally first, make a file at
`.streamlit/secrets.toml` with the same three lines, then run:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

---

## How the app works, in plain language

**1. It downloads the day's one-minute price bars.**
For your ticker, plus SPY and QQQ. Each bar says: during this minute, the
price opened here, went this high, this low, closed here, and this much
volume traded.

**2. It calculates VWAP.**
VWAP is the average price paid so far today, weighted by volume, so minutes
with heavy trading count more than quiet ones. It resets at the start of
every session. Traders watch it because it is roughly the average price
everyone else today has paid.

The app adds up (price × volume) for every minute, then divides by total
volume. If the regular session has not opened yet, it uses premarket bars
instead and says so on screen.

**3. It decides your stock's VWAP state.**

- **Above VWAP** – price is more than 0.10% above the line
- **Below VWAP** – price is more than 0.10% below the line
- **Reclaiming VWAP** – price is above now, but was below within the last
  10 minutes
- **Rejecting VWAP** – price is below now, but was above within the last
  10 minutes
- **At VWAP (watch area)** – price is within 0.10% of the line, so nothing
  is settled

**4. It finds SPY and QQQ premarket levels.**
It takes every bar between your chosen start time (4:00 AM or 7:00 AM ET)
and the 9:30 AM open, then records the highest high and the lowest low. Those
two numbers are the premarket range. Price above the high, below the low, or
inside the range gives you the index state.

**5. It combines everything into one summary.**
Bullish readings score positive, bearish score negative, neutral scores zero.
Your stock counts double, because it is what you are actually watching.

- Everything leaning the same way → **green, bullish or bearish context**
- Your stock and the indices disagreeing → **yellow, mixed context**
- Nothing leaning either way → **gray, neutral context**

**6. It refreshes itself.**
Every 30 to 60 seconds, depending on your slider, the page reloads and does
all of the above again. Results are cached between refreshes so it does not
waste API calls.

---

## The sidebar settings

| Setting | What it does |
| --- | --- |
| **Ticker you are watching** | The main stock. Type any US symbol: NVDA, TSLA, AAPL, AMD |
| **Data mode** | Demo mode uses sample data and needs no key. Live mode uses real data |
| **Demo scenario** | Only in demo mode. Switch between Bullish, Bearish, Mixed and Neutral to see how the display changes |
| **Premarket window starts at** | 4:00 AM ET catches the full premarket. 7:00 AM ET gives a tighter, more recent range |
| **Auto-refresh every** | 30 to 60 seconds. Use 60 on a free data plan |
| **Show change alerts** | Logs it when a VWAP or range state flips |
| **Show price vs VWAP chart** | Turn the chart on or off |
| **Refresh now** | Forces an immediate update |

---

## Troubleshooting

**"No API key found"**
You are in Live mode without a key in secrets. Either add `polygon_api_key`
in Settings → Secrets, or switch the sidebar to Demo mode.

**"The data provider rejected your API key"**
The key is wrong, has extra spaces, or is missing its quotation marks in the
secrets box. Copy it again from your dashboard. Also check your plan actually
covers stock data.

**"Rate limit reached"**
Too many requests per minute. Free plans allow about 5 and this app uses 3
per refresh. Set the refresh slider to 60 seconds and wait a minute.

**"Showing the last available session, not today"**
Not an error. Either the market is closed today, or your data plan does not
include today's intraday bars. Everything on screen is real, it is just from
the previous session.

**"No price data came back for ..."**
Check the ticker spelling. Delisted symbols and non-US symbols will not work.
Demo mode always works, so use it to confirm the app itself is fine.

**Premarket high and low both show `--`**
There were no premarket trades in your chosen window. Try switching the
premarket start to 4:00 AM ET, which captures more of the session.

**The app says "Oh no. Error running app"**
Usually a missing library. Check `requirements.txt` uploaded correctly. To see
the real error, open `.streamlit/config.toml` in GitHub, change
`showErrorDetails = false` to `true`, commit, and reload the app.

**"ModuleNotFoundError: No module named 'vwap_agent'"**
The `vwap_agent` folder did not upload, or its files sit loose in the repo
root. In GitHub you should see a folder named `vwap_agent` containing
`config.py`, `context.py`, `demo_data.py`, `indicators.py`, `market_data.py`,
`ui.py` and `__init__.py`.

**The page does not refresh by itself**
Check `streamlit-autorefresh` is in `requirements.txt`. The app falls back to
reloading the browser tab if that package is missing, which some browsers
block. The **Refresh now** button always works.

**I forgot my password**
Go to Settings → Secrets, change `app_password` to something new, and save.

**The app is asleep**
Free apps sleep after a few days idle. Click the wake button and wait.

**It looks cramped on my phone**
Tap the **>** arrow at the top left to open and close the sidebar. The cards
stack automatically on narrow screens.

---

## Project structure

```
vwap-market-context-agent/
├── streamlit_app.py          # The app itself: password, sidebar, layout
├── requirements.txt          # Libraries Streamlit needs to install
├── README.md                 # This file
├── .gitignore                # Stops secrets being uploaded by accident
├── .streamlit/
│   ├── config.toml           # Colours and display settings
│   └── secrets.toml.example  # Template. Copy it, never commit the real one
└── vwap_agent/
    ├── __init__.py
    ├── config.py             # Settings: times, colours, wording, thresholds
    ├── market_data.py        # Downloads price bars, handles errors
    ├── demo_data.py          # Builds sample data for demo mode
    ├── indicators.py         # VWAP and premarket maths
    ├── context.py            # Writes the plain-English summary
    └── ui.py                 # Cards, colours, styling
```

---

## Changing things later

- **Different colours** – edit the colour codes at the top of
  `vwap_agent/config.py`
- **A wider or narrower "at VWAP" zone** – change `VWAP_NEUTRAL_BAND_PCT`
  in `config.py`. `0.0010` means 0.10%
- **A longer memory for reclaim and reject** – change `CROSS_LOOKBACK_BARS`
  in `config.py`
- **Different wording** – all the sentences live in `vwap_agent/context.py`

After any edit, commit the change on GitHub. The website rebuilds itself
within a minute.

---

## Disclaimer

This software is provided for education and general information only. It
performs no trading, holds no brokerage connection, and makes no
recommendation to buy or sell any security. Market data may be delayed or
incomplete. Past behaviour of any indicator does not indicate future results,
and no profit or outcome is implied or promised. You are solely responsible
for your own decisions. If you need advice, speak to a licensed professional.
