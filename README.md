# Virtual Work Environment (Venv)

منصة عربية تحاكي بيئة العمل للطلاب وحديثي التخرج. تحلل السيرة الذاتية، تحدد المستوى عبر 10 أسئلة، تبني مسارًا مهنيًا، ثم تدير مهمة واحدة في كل مرة بواسطة Manager وMentor وHR.

## المتطلبات

- Docker Desktop
- Git
- مفتاح OpenAI اختياري؛ بدونه يعمل النظام بالردود التجريبية

## التشغيل لأول مرة

```bash
git clone https://github.com/Faisal-Alrashed1/Virtual-Work-Environment.git
cd Virtual-Work-Environment
cp .env.example .env
docker compose up --build
```

إذا أردت تشغيل الذكاء الاصطناعي الحقيقي، افتح ملف `.env` وضع المفتاح بعد علامة `=`:

```env
OPENAI_API_KEY=ضع_مفتاحك_هنا
```

ملف `.env` مستبعد من Git، لذلك لا يُرفع إلى GitHub. لا تضع المفتاح في `.env.example` أو داخل الكود.

بعد ظهور رسالة `Ready` افتح:

- الموقع: http://localhost:3000
- توثيق API: http://localhost:8000/docs

## أوامر الاستخدام

```bash
# تشغيل لاحق في الخلفية
docker compose up -d

# عرض الحالة
docker compose ps

# عرض السجلات
docker compose logs -f

# إيقاف المشروع
docker compose down

# إعادة البناء بعد تعديل الكود
docker compose up -d --build
```

على macOS يجب أن يكون Docker Desktop مفتوحًا وتظهر حالة `Engine running` قبل التشغيل.

## تجربة النظام

1. أنشئ حسابًا وارفع CV بصيغة PDF أو DOCX، بحد أقصى 8MB.
2. أجب عن 10 أسئلة تحديد المستوى، ثم اكتب هدفك بصراحة.
3. أنشئ المسار وابدأ المهمة التي يرسلها Manager.
4. استشر Mentor، ثم سلّم رابط GitHub وناقش النتيجة.
5. راجع تقييمات Manager وMentor وHR ثم انتقل للمهمة التالية.

## البنية التقنية

- `apps/web`: واجهة Next.js وReact.
- `apps/api`: خلفية FastAPI وPython والوكلاء ودورة المهام.
- `db`: PostgreSQL مع pgvector داخل Docker.
- `infra`: تهيئة قاعدة البيانات.

## الاختبارات

```bash
docker compose exec api sh -lc "PYTHONPATH=/app pytest -q"
```

## حل المشاكل السريع

- `docker: command not found`: افتح Docker Desktop ثم أعد فتح Terminal.
- `connection refused`: نفذ `docker compose ps` وتأكد أن `web` و`api` و`db` تعمل.
- `Load failed`: افحص `docker compose logs api` وتأكد من صحة `.env`.
- بعد تغيير المفتاح: نفذ `docker compose up -d --force-recreate api`.
