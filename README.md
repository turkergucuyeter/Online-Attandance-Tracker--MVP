# Online Yoklama Takip Sistemi (MVP)

Okullarda devamsızlık süreçlerini sade ve güvenli biçimde yönetmek için tasarlanmış web tabanlı bir yoklama takip uygulaması.

## Özellikler

### Kullanıcı Rollerine Göre İmkanlar

- **Yönetici (Supervisor)**
  - Öğretmen, ders, sınıf ve öğrenci yönetimi (ekleme/düzenleme/silme).
  - CSV veya PDF formatındaki öğrenci listelerini içeri aktarma.
- Öğrenciler için isteğe bağlı olarak giriş hesabı (e-posta/şifre) oluşturma veya güncelleme.
  - Boş bırakılan e-posta / şifre alanları için otomatik öğrenci kimlik bilgileri üretme.
  - Öğretmenlerin aldığı yoklamaları görüntüleme, filtreleme ve düzenleme.
  - Yoklama kayıtlarını CSV veya PDF olarak dışa aktarma.
- **Öğretmen**
  - Yetkili olduğu ders ve sınıflar için yoklama oluşturma.
  - Öğrenci durumlarını (Var / Mazeretli / Mazeretsiz) düzenleme.
  - Kaydedilen yoklamaları 30 dakika içinde güncelleme.
  - Kendi yoklama geçmişini görüntüleme.
- **Öğrenci**
  - Ders bazlı devamsızlık durumunu ve yüzdelerini takip etme.
  - Belirlenen mazeretli / mazeretsiz sınırları aşıldığında uyarı alma.

## Kurulum

> Gereksinimler: Python 3.10+, pip, virtualenv (önerilir)

```bash
python -m venv venv
source venv/bin/activate  # Windows için: venv\Scripts\activate
pip install -r requirements.txt
```

### Veritabanı ve Yönetici Hesabı Oluşturma

```bash
python -m app.init_db
```

Komut sizi ilk yönetici (supervisor) kullanıcıyı oluşturmanız için yönlendirecektir.

## Uygulamayı Çalıştırma

```bash
flask --app wsgi run
```

Varsayılan olarak uygulama `http://127.0.0.1:5000` adresinde çalışır. Çalışan uygulamayı farklı bir portta başlatmak için `--port` parametresini kullanabilirsiniz.

## Rol Bazlı Giriş

| Rol | Giriş Adresi |
| --- | --- |
| Yönetici | `http://127.0.0.1:5000/auth/login` |
| Öğretmen | `http://127.0.0.1:5000/auth/login` |
| Öğrenci | `http://127.0.0.1:5000/auth/login` |

Sistem tüm kullanıcılar için aynı giriş sayfasını kullanır; rol farkı giriş yaptıktan sonra otomatik olarak yönlendirilir.

## CSV / PDF İçeri Aktarma Formatı

Dosyalar aşağıdaki başlıklara sahip bir tablo içermelidir:

```
ad, soyad, okul_numarasi, sinif
```

PDF içe aktarma özelliği; satırların bu başlıklarla yapılandırıldığı, tablo biçimindeki dokümanlar ile uyumludur.

## Otomatik Öğrenci Hesapları ve İndirme

- Yönetici panelinden öğrenci eklerken/düzenlerken e-posta veya şifre alanı boş bırakıldığında sistem otomatik olarak `ogrenci.okul` alan adında benzersiz bir e-posta ve güçlü bir şifre üretir.
- Oluşturulan bilgiler, sayfanın üst kısmındaki "Oluşturulan Öğrenci Kimlik Bilgileri" kartında listelenir ve yalnızca mevcut oturum boyunca saklanır.
- Kart üzerindeki **CSV Olarak İndir** bağlantısını kullanarak tüm üretilen kimlik bilgilerini tek seferde dışa aktarabilir, dosyayı güvenli biçimde paylaşabilirsiniz.
- Listede hangi bilgilerin otomatik oluşturulduğu rozetlerle belirtilir; manuel girilen değerler "Hayır" olarak işaretlenir.

## Güvenlik Notları

- Parolalar güvenli şekilde hashlenerek veritabanında saklanır.
- Rol tabanlı yetkilendirme denetimleri ile her kullanıcı yalnızca kendi izni olan sayfalara erişebilir.
- Öğretmenler yalnızca yetkili oldukları sınıf/ders kombinasyonlarında yoklama alabilir.

## Geliştirme İpuçları

- Varsayılan olarak SQLite veritabanı (`attendance.db`) kullanılır. Farklı bir veritabanı kullanmak isterseniz `DATABASE_URL` ortam değişkenini ayarlayabilirsiniz.
- Gizli anahtarı (`SECRET_KEY`) üretim ortamında mutlaka değiştirin.
- Statik dosyalar ve şablonlar tamamen Türkçe arayüz için hazırlandı ve Bootstrap 5 ile responsive olacak şekilde düzenlendi.

## Test Kullanıcıları Oluşturma (Opsiyonel)

Yönetici panelinden yeni öğretmen ve öğrenci hesapları oluşturabilir, öğrencilere kullanıcı hesabı tanımlamak için aynı e-posta ile yeni kullanıcı oluşturup ilgili öğrenci kaydına iliştirebilirsiniz.

## Lisans

Bu proje eğitim kurumlarında ücretsiz kullanım için geliştirilmiştir.
