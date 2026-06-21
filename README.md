# যোগদানপত্র জেনারেটর (PDF, no-print-dialog) rasel

ফর্ম পূরণ করুন → "PDF ডাউনলোড করুন" বাটনে ক্লিক করুন → A4 সাইজের আসল ভেক্টর PDF সরাসরি ডাউনলোড হয়ে যাবে। কোনো ব্রাউজার প্রিন্ট ডায়ালগ আসবে না।

## এটা কীভাবে কাজ করে

- ফর্ম পেজ (`templates/index.html`) আগের মতই — টাইপ করলে ডানপাশে প্রিভিউ আপডেট হয়।
- "PDF ডাউনলোড করুন" বাটনে ক্লিক করলে ফর্মের ডেটা ব্যাকএন্ডে (`/generate-pdf`) পাঠানো হয়।
- ব্যাকএন্ড (FastAPI + Playwright/Chromium) সার্ভার সাইডে চিঠিটা রেন্ডার করে, ব্রাউজারের প্রিন্ট ইঞ্জিন দিয়েই (headless Chromium) সরাসরি ভেক্টর PDF বানায় — তাই কোয়ালিটি Word/PDF প্রিন্টের মতই ভালো, ছবির মতো ব্লার হয় না।
- কোনো ডেটা সার্ভারে সেভ থাকে না — প্রতিটা request স্টেটলেস। একসাথে অফিসের কয়েকজন ব্যবহার করলেও কোনো সমস্যা হবে না।

## লোকালি রান করা (টেস্ট করার জন্য)

```bash
pip install -r requirements.txt
python -m playwright install chromium
uvicorn app.main:app --reload
```

তারপর ব্রাউজারে `http://localhost:8000` খুলুন।

## GitHub এ পুশ করা

```bash
cd joydan-pdf-app
git init
git add .
git commit -m "যোগদানপত্র জেনারেটর - PDF backend সহ"
git branch -M main
git remote add origin https://github.com/<আপনার-ইউজারনেম>/<রিপো-নাম>.git
git push -u origin main
```

## Railway তে ডিপ্লয় করা

1. [railway.app](https://railway.app) এ যান, GitHub দিয়ে লগইন করুন।
2. **New Project → Deploy from GitHub repo** সিলেক্ট করুন, এই রিপোটা বেছে নিন।
3. Railway নিজেই `Dockerfile` দেখে ডিটেক্ট করে নেবে এবং বিল্ড শুরু করবে (Playwright এর অফিসিয়াল Docker image ব্যবহার হচ্ছে, তাই Chromium আগে থেকেই ইনস্টলড থাকবে — আলাদা কিছু সেটআপ করতে হবে না)।
4. বিল্ড শেষ হলে **Settings → Networking → Generate Domain** চাপুন। একটা পাবলিক URL পেয়ে যাবেন (যেমন `https://your-app.up.railway.app`)।
5. সেই URL অফিসের সবাইকে শেয়ার করুন — সবাই একসাথে ব্যবহার করতে পারবে, প্রতিটা ব্যবহারকারীর জন্য আলাদা সেশন/ডেটা সেভ লাগবে না।

### Environment variable

`PORT` — Railway নিজে থেকেই সেট করে দেয়, আলাদা করে কিছু করতে হবে না।

## ফাইল স্ট্রাকচার

```
joydan-pdf-app/
├── app/
│   └── main.py          # FastAPI app: রুট + PDF জেনারেশন লজিক
├── templates/
│   ├── index.html        # ব্যবহারকারীর দেখা ফর্ম পেজ
│   └── letter.html        # শুধু চিঠির HTML — Playwright এটা রেন্ডার করে PDF বানায়
├── requirements.txt
├── Dockerfile
├── railway.json
└── README.md
```

## যদি ফন্ট বা লেআউট নিয়ে সমস্যা হয়

- ডিফল্ট ফন্ট Noto Sans Bengali — সবচেয়ে নিরাপদ ও পরিষ্কার।
- SutonnyMJ একটা পুরনো ANSI ফন্ট (Unicode না), তাই Unicode বাংলা টেক্সটের সাথে ঠিকভাবে কাজ করবে না — সিলেক্ট করলে ফর্মেই warning দেখাবে।
- চিঠি যদি এক পেজের বেশি বড় হয়ে যায়, এখন আর auto-shrink হয় না (আগের ছবি-ভিত্তিক ভার্সনে ছিল) — কারণ এখন real multi-page vector PDF হিসেবেই বানায়; চিঠি বড় হলে ২য় পেজে চলে যাবে, যেটা Word ডকুমেন্টের স্বাভাবিক আচরণ।
