# Bundled fonts

Geist and Geist Mono, served by Streamlit's static file serving (`server.enableStaticServing` in
`.streamlit/config.toml`, URL `app/static/fonts/...`) so the dashboard looks the same without a network.

| File | Font | Version | Source (google/fonts, pinned commit) | sha256 |
|---|---|---|---|---|
| `Geist-Variable.ttf` | Geist, variable weight 100–900 | 1.800 | `ofl/geist/Geist[wght].ttf` at `718e1db4deb9e4d9d85a0ead1b9f5fde2761ccfd` | `73894e0448cae90a92b6c2f8732b7bb9acb7b94c418bff559dad4a18e1de9659` |
| `GeistMono-Variable.ttf` | Geist Mono, variable weight 100–900 | 1.701 | `ofl/geistmono/GeistMono[wght].ttf` at `9e25e2ba265e5298f70f6182dd4e8a3ebf1b9123` | `d00e590b8eb3a59acc329b2d044fd143ae935090b7da33199ebee27cc7de8196` |

The files are unmodified (only renamed). Licence: SIL Open Font License 1.1, Copyright 2024 The Geist
Project Authors (https://github.com/vercel/geist-font); the full text is in `OFL.txt` (identical for both
families upstream).
