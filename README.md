# Media Drop

**Media Drop** is a desktop application with a web interface designed for downloading media from various online services.

The main idea of the project is simple: **download almost anything from almost anywhere** through one convenient interface.

> ⚠️ **Early Development:** Media Drop is currently in active development. Some services may not work yet, and some features are still experimental.

---

## ✨ Features

* 🎬 Download videos
* 🎵 Download audio
* 🌐 Support for multiple online services
* 🔍 Automatic service detection from a pasted link
* 📋 Download history
* 🖥️ Web-based interface running locally on your computer
* 🔄 Different services can be handled through a single application

---

## 🌐 Supported Services

### ✅ Currently Available

* **YouTube**

  * Video downloads
  * Audio downloads
* **Spotify**

  * Audio downloads

### ❌ Currently Unavailable

The following services are **not supported yet**:

* TikTok
* VK
* SoundCloud
* Instagram
* Other services that are not currently implemented

Support for additional platforms will be added in future updates.

---

## 🖥️ How It Works

Media Drop is designed to run **locally on your computer**.

The application starts a local web server, which you access through your browser.

**Important:** the program works only while its CMD/terminal window is running.

If you close the CMD window, the Media Drop server will stop and the web interface will no longer work.

---

## 🚀 How to Launch

### Firefox

The easiest way to start Media Drop is to run:

```text
start.bat
```

After launching, the application will start automatically and open in Firefox.

> Currently, `start.bat` is intended to be used with **Firefox**.

### Other Browsers

If you want to use Chrome, Edge, or another browser:

1. Open the Media Drop folder.
2. Click the address bar in Windows Explorer.
3. Type:

```text
cmd
```

4. Press **Enter**.
5. Run:

```bash
python app.py
```

6. Wait until the program starts.
7. Copy the local address shown in the CMD window.
8. Open this address in your browser.

Keep the CMD window open while using Media Drop.

---

## 🇷🇺 Важная информация для пользователей из РФ

**Для жителей РФ:**

Media Drop **не обходит блокировки и не предоставляет доступ к заблокированным сервисам**.

Программа сможет скачивать контент с определённого сервиса только в том случае, если **у вас уже есть доступ к этому сервису с вашего компьютера и вашей сети**.

Например:

> Если вы не можете открыть YouTube со своего компьютера, Media Drop также не сможет получить доступ к YouTube.

То есть Media Drop использует доступ к интернету, который уже есть у вашего компьютера. Программа не предназначена для автоматического обхода блокировок, региональных ограничений, цензуры или других сетевых ограничений.


---

## 🛠️ Planned Features

The project is still being developed. The following improvements are planned:

* 🌍 **Language selection**

  * Ability to change the interface language.
  * Additional languages in the future.

* 🚀 **More convenient application launch**

  * Easier startup process.
  * Automatic browser launch.
  * Less manual interaction with CMD.

* 📦 **Requirements / dependency improvements**

  * Simplify the installation of required Python packages.
  * Fix current issues related to `requirements.txt`.
  * Make the initial setup easier for new users.

* 🌐 **More supported services**

  * TikTok
  * VK
  * SoundCloud
  * Instagram
  * Other platforms

* 🐛 **Bug fixes and stability improvements**

---

## 📌 Current Status

**Version:** `0.1`

**Status:** 🚧 Early Development

Media Drop is currently an experimental project. Some functionality may not work correctly, and compatibility with different services and browsers may change between releases.

More features and improvements are planned for future versions.

---

## 💡 Project Goal

The long-term goal of Media Drop is to provide a **single, simple application for downloading media from many different platforms** without having to use a separate downloader for every service.

**One application. One interface. Multiple services.**
