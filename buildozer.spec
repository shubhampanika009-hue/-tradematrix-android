[app]
title = TradeMatrix
package.name = tradematrix
package.domain = org.tradematrix
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt,json
version = 0.2

requirements = python3,kivy==2.3.0,kivymd==1.2.0,pillow,certifi,pyjnius,android

orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api = 34
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
