# AgentHub Frontend

This is the frontend application for AgentHub, a platform for managing and running AI agents with various tools and capabilities.

## Setup and Installation

1. Install dependencies:

```bash
cd frontend
npm install
# or if you use yarn
yarn
```

2. Make sure to specifically install Heroicons (in case of any issues):

```bash
npm install @heroicons/react@latest
# or with yarn
yarn add @heroicons/react@latest
```

3. Run the development server:

```bash
npm run dev
# or with yarn
yarn dev
```

4. Build for production:

```bash
npm run build
# or with yarn
yarn build
```

## Folder Structure

- `public/` - Static assets
- `src/` - Source code
  - `components/` - Reusable UI components
  - `pages/` - Page-level components
  - `services/` - API service layer
  - `App.jsx` - Root component
  - `main.jsx` - Entry point

## Available Scripts

- `dev` - Start the development server
- `build` - Build for production
- `lint` - Lint the code
- `preview` - Preview the production build

## Environment Variables

Create a `.env` file with the following variables:

```
VITE_API_BASE_URL=http://localhost:8000/api
```

## Troubleshooting

If you encounter issues with Heroicons imports, try the following steps:

1. Make sure you have the latest version installed:
   ```bash
   npm install @heroicons/react@latest
   ```

2. Check the correct import syntax:
   ```javascript
   // Use the correct import syntax
   import { HomeIcon } from '@heroicons/react/24/outline';
   ```

3. Restart the development server:
   ```bash
   npm run dev
   ```

4. If problems persist, you may need to clear the Vite cache:
   ```bash
   rm -rf node_modules/.vite
   ```

## Icons Alternative

If you continue to have issues with Heroicons, you can alternatively use React Icons as a replacement:

```bash
npm install react-icons
# or with yarn
yarn add react-icons
```

Then update your imports to use React Icons instead:

```javascript
import { FiHome, FiMenu, FiX, FiCpu, FiCode, FiFlask } from 'react-icons/fi';
```
