# Engoo Daily News → GitHub (אוטומטי כל בוקר)

פרויקט שמוריד **כל בוקר** 3 כתבות חדשות מכל נושא מ-Engoo Daily News (רמות 4–9) ושומר אותן כקבצי טקסט בתיקיות לפי נושא.

## מבנה התיקיות

```
├── Business_Politics/
├── Science_Technology/
├── Health_Lifestyle/
├── Culture_Society/
├── Travel_Experiences/
├── scripts/fetch_daily.py
└── .github/workflows/daily.yml   ← רץ כל בוקר אוטומטית
```

שם הקובץ: `שם_הכתבה_levelX.txt`  
תוכן: כותרת + רמה + תאריך + גוף הכתבה המלא (בלי שאלות).

## איך להפעיל אצלך ב-GitHub (5 דקות)

1. **צור ריפו חדש** ב-GitHub (מומלץ Public או Private – לא משנה).
2. העלה את כל התוכן של התיקייה הזו לריפו (או clone ואז העתק את הקבצים).
3. לך ל-**Settings → Actions → General** וודא ש-Actions מופעלים (Allow all actions).
4. לך ל-**Actions** → בחר את ה-workflow "Daily Engoo News" → **Run workflow** (פעם ראשונה ידנית).
5. מהיום והלאה זה ירוץ **אוטומטית כל יום ב-05:00 UTC** (בערך 07:00–08:00 שעון ישראל).

אין צורך ב-Secrets – ה-API של Engoo פתוח.

## הרצה ידנית מקומית

```bash
pip install requests
python scripts/fetch_daily.py
```

הסקריפט בודק אילו כתבות כבר קיימות בתיקיות ולא מוריד כפילויות.

## שינוי הגדרות

בקובץ `scripts/fetch_daily.py`:

- `ARTICLES_PER_TOPIC = 3`  ← כמה כתבות לכל נושא
- `MIN_LEVEL / MAX_LEVEL`   ← רמות
- השעה ב-`.github/workflows/daily.yml` (cron)

---

נוצר עבור שימוש אישי / לימודי.
