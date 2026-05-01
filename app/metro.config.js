const { getDefaultConfig } = require('expo/metro-config');
const { withNativeWind } = require('nativewind/metro');

const config = getDefaultConfig(__dirname);

// expo-sqlite's web shim needs to import wa-sqlite.wasm
config.resolver.assetExts = [...(config.resolver.assetExts || []), 'wasm'];

// expo-sqlite on web uses wa-sqlite which requires SharedArrayBuffer.
// SharedArrayBuffer needs cross-origin isolation headers (COOP + COEP).
config.server = {
  ...config.server,
  enhanceMiddleware: (middleware) => {
    return (req, res, next) => {
      res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
      res.setHeader('Cross-Origin-Embedder-Policy', 'require-corp');
      return middleware(req, res, next);
    };
  },
};

module.exports = withNativeWind(config, { input: './global.css' });
