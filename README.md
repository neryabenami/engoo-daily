# Engoo Daily News → GitHub (אוטומטי כל בוקר)

פרויקט שמוריד **כל בוקר** 3 כתבות חדשות מכל נושא מ-Engoo Daily News (רמות 4–9)  
ושומר אותן כקבצי טקסט בתיקיות לפי נושא.

## מה השתפר בגרסה הזו (עמידות)

- **Retries אוטומטיים** (3 ניסיונות) על שגיאות רשת / timeout / 429
- זיהוי ברור של חסימה (403/401) ושל שינוי במבנה ה-API
- לוג מפורט + קובץ `status.json` ו-`last_run.txt` אחרי כל ריצה
- גם אם חלק מהנושאים נכשלים – השאר ממשיכים והסטטוס נשמר
- ה-workflow מעלה את הלוגים כ-Artifact (נשמר 14 יום) – נוח לבדיקה
- אם Engoo ישנו את ה-API לגמרי – תקבל הודעה ברורה בלוג במקום כשל מסתורי

## מבנה

```
├── Business_Politics/
├── Science_Technology/
├── Health_Lifestyle/
├── Culture_Society/
├── Travel_Experiences/
├── scripts/fetch_daily.py
├── status.json          ← נוצר אחרי כל ריצה
├── last_run.txt
└── .github/workflows/daily.yml
```

שם הקובץ: `שם_הכתבה_levelX.txt`  
תוכן: כותרת + רמה + תאריך + גוף הכתבה המלא (בלי שאלות).

## איך להפעיל (5 דקות)

1. צור ריפו חדש ב-GitHub.
2. העלה את כל התוכן של התיקייה הזו.
3. Settings → Actions → General → אפשר Actions.
4. Actions → "Daily Engoo News" → **Run workflow** (פעם ראשונה ידנית).
5. מהיום זה רץ לבד כל לילה ב-01:00 UTC (03:00 שעון ישראל בחורף).

אין צורך ב-Secrets.

## מה קורה כשמשהו נשבר?

| מצב                        | מה תראה                          | מה לעשות                     |
|---------------------------|----------------------------------|------------------------------|
| Engoo חסמו / שינו API     | הודעה ברורה ב-`status.json` + לוג | לפנות אליי / לעדכן את הסקריפט |
| אין כתבות חדשות היום      | `added: 0`, Success=true         | תקין – אין מה לעשות          |
| שגיאת רשת זמנית           | Retries אוטומטיים                | בדרך כלל נפתר לבד            |
| כשל חלקי בנושא אחד        | הנושאים האחרים ממשיכים           | בדוק את `status.json`        |

אחרי כל ריצה אפשר גם להוריד את ה-Artifact בשם `engoo-daily-logs` מתוך דף ה-Actions.

## הרצה מקומית

```bash
pip install requests
python scripts/fetch_daily.py
```

## שינוי הגדרות

ב-`scripts/fetch_daily.py`:
- `ARTICLES_PER_TOPIC = 3`
- `MIN_LEVEL` / `MAX_LEVEL`
- `MAX_RETRIES` / `RETRY_DELAY`

ב-`.github/workflows/daily.yml` – שעת ה-cron.

---
