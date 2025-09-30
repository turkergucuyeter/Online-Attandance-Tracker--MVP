# Online Yoklama Takip Uygulaması (MVP)

Bu depo, manuel yoklama ile çalışan, Supervisor/Öğretmen/Öğrenci rollerine sahip, devamsızlık yüzdesini hesaplayıp uyarı veren, feature-flag destekli bir MVP içerir. Proje paket bağımlılıkları olmadan (yalnızca Python standart kütüphanesi ile) çalışacak şekilde tasarlandı, bu sayede ek kurulum gerektirmeden hızlıca devreye alınabilir.

## İçerik

- **backend/** – Python ile yazılmış REST API, SQLite veritabanı, migrasyonlar, seed verisi ve OpenAPI dokümanı.
- **frontend/** – Modern görünümlü, vanilla JS ile yazılmış, rol bazlı yönlendirme yapan arayüz.
- **prisma/postgres_schema.sql** – PostgreSQL’e geçiş için hazır şema dosyası.
- **.env.example** – Ortam değişkenleri örneği.

## Kurulum Adımları

> ⚠️ Projede harici paket kullanılmadığı için yalnızca Python 3.11+ gereklidir.

1. Depoyu klonlayın ve klasöre geçin.
   ```bash
   git clone <repo-url>
   cd Online-Attandance-Tracker--MVP
   ```

2. Ortam değişkenlerini düzenleyin (opsiyonel).
   ```bash
   cp .env.example .env
   # JWT_SECRET gibi değerleri ihtiyaçlarınıza göre düzenleyin.
   ```

3. Veritabanını oluşturup demo verilerini yükleyin.
   ```bash
   python -m backend.seed
   ```

4. API’yi başlatın.
   ```bash
   python -m backend.app
   ```
   Sunucu varsayılan olarak `http://localhost:8000` adresinde dinler.

5. Frontend’i servis edin.
   ```bash
   cd frontend
   python -m http.server 5173
   ```
   Ardından tarayıcıdan `http://localhost:5173` adresine giderek giriş yapabilirsiniz.

## Demo Kullanıcıları

| Rol        | E-posta                  | Şifre            |
|------------|--------------------------|------------------|
| Supervisor | supervisor@example.com   | Supervisor123!   |
| Öğretmen   | teacher@example.com      | Teacher123!      |
| Öğrenci    | student@example.com      | Student123!      |

## Özellikler

### Supervisor Paneli
- Öğretmen, öğrenci, sınıf, ders ve dönem CRUD işlemleri.
- Öğretmenlere renk atama (listelerde renk rozeti olarak gösterilir).
- Ders oturumu planlama, feature flag yönetimi ve CSV/JSON raporları.
- Tüm mutasyonlar `audit_logs` tablosuna yazılır.

### Öğretmen Paneli
- Renkli sınıf kartları.
- Her sınıf için güncel oturum listesi.
- Ders saati içinde manuel yoklama alma/güncelleme (grace period flag’i destekli).
- Yoklama kaydı sonrası devamsızlık yüzdesi hesaplanır, eşik aşılırsa öğrenciye bildirim gönderilir.

### Öğrenci Paneli
- Ders bazlı devamsızlık yüzdeleri ve eşik bilgisi.
- Eşik aşımında uyarı şeridi ve bildirim kartları.

### Bildirimler
- `notifications` tablosu hem in-app hem web push (ücretsiz kabulüyle) kayıtları tutar.
- Arayüzde okunmamış bildirim sayısı, kullanıcı menüsünde rozet olarak gösterilir.

### Feature Flags
- `absence_only_unexcused`: Devamsızlık yüzdesine sadece “izinsiz” kayıtları dahil et.
- `attendance_grace_period`: Ders bitiminden sonra kaç dakika güncelleme yapılabileceğini belirler.

## API Dokümantasyonu

- `backend/openapi.yaml` dosyası tüm uç noktaları özetleyen OpenAPI 3.0 şeması içerir.
- İsteğe bağlı olarak `redocly` veya başka bir araç ile görselleştirilebilir.

## Veritabanı

- Varsayılan olarak SQLite (`backend/app.db`).
- PostgreSQL’e geçiş için `prisma/postgres_schema.sql` dosyasını kullanabilirsiniz.
- Migrasyonlar `backend/migrations/` altında SQL olarak tutulur, `python -m backend.migrate` ile çalıştırılabilir.

### Örnek Şema (SQLite)
Tablolar kullanıcılar, öğretmen/öğrenci rolleri, sınıflar, dersler, dönemler, oturumlar, yoklamalar, feature flag’ler, audit log’lar ve bildirimleri kapsar.

## Test & Kalite

- Proje standart kütüphane ile yazıldığı için ek bağımlılık yoktur.
- Giriş kontrolü ve RBAC, JWT ile sağlanır (HS256).
- Şifreler PBKDF2 (sha256) ile salt’lı olarak saklanır.
- Tarihler SQLite üzerinde UTC olarak tutulur ve arayüzde yerel formatta gösterilir.

## Geliştirme Önerileri

- Frontend komponentleri modern çerçevelere (React vb.) taşınabilir; API sözleşmesi stabildir.
- Web push gerçekleme için `notifications` tablosundaki `webpush` kayıtları kullanılabilir.
- CI/CD’de `python -m backend.seed` ve `python -m backend.app` komutları ile smoke test yapılabilir.

## Lisans

Bu MVP eğitim amaçlıdır. İsterseniz ticari projelerinizde temel olarak kullanabilir, ihtiyaçlarınıza göre genişletebilirsiniz.
