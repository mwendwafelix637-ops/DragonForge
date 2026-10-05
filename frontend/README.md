# DragonForge frontend

`client/` is the active React/Vite owner console. It calls the DragonForge Platform API at `/api/v1`; the Vite development proxy forwards those requests to `http://localhost:8000`.
After owner sign-in, **FX reference rates** shows official daily ECB reference values for selected major currencies. These are not live trading quotes; details and coverage limits are shown in the screen.
The **Global macro indicators** page shows annual World Bank inflation and real GDP growth observations for selected economies; it is historical data, not a real-time signal.

For setup, database migrations, and local startup instructions, follow [the Platform API guide](../platform_api/README.md). The client can also be started from the repository root with:

```bash
npm --prefix frontend/client ci
npm --prefix frontend/client run dev -- --host 0.0.0.0
```

To point the development client at a different API, set `DRAGONFORGE_API_PROXY_TARGET` before starting Vite.

`server/` is a separate legacy NeuroLens results API that reads the research JSON files in the root `results/` directory. It is not used by the active DragonForge owner console. To run it independently:

```bash
npm --prefix frontend/server ci
npm --prefix frontend/server run dev
```

It listens on port 3001 by default and exposes legacy research routes under `/api/`. Those routes are not DragonForge market data or live trading functionality.
