# APEX-UI attribution for the Z.A.R.V.I.S. HUD

The Z.A.R.V.I.S. agent HUD in `zworkforce/static/zarvis-hud.{js,css}` is an independent zWorkforce implementation adapted from interaction and visual-design patterns in [`RubenM1990/APEX-UI`](https://github.com/RubenM1990/APEX-UI).

APEX-UI is distributed under the MIT License:

> Copyright (c) 2026 Ruben Mouradian (Reznikov Engineering)
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, subject to inclusion of the copyright and permission notice.

The zWorkforce implementation intentionally does **not** reuse the Apex product name, Reznikov Engineering branding, WebGL shader background, or overview lamp component. It uses dependency-free SVG/CSS/JavaScript to express the following reusable interaction ideas:

- concentric autonomous-assistant orb presentation;
- agent/reasoning constellation around the assistant core;
- keyboard-selectable agent overview nodes;
- runtime/state status strip;
- `prefers-reduced-motion` support.

The existing zWorkforce Z.A.R.V.I.S. voice transport, one-time ticket handling, push-to-talk lifecycle, mutation approval policy, tenant authorization, and server-side credential boundaries remain authoritative and are not derived from APEX-UI.
