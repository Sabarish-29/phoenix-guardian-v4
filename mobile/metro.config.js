const { getDefaultConfig, mergeConfig } = require('@react-native/metro-config');

/**
 * Metro configuration for Phoenix Guardian Mobile
 * https://facebook.github.io/metro/docs/configuration
 */

const defaultConfig = getDefaultConfig(__dirname);

const config = {
  transformer: {
    getTransformOptions: async () => ({
      transform: {
        experimentalImportSupport: false,
        inlineRequires: true,
      },
    }),
  },
  resolver: {
    sourceExts: [...defaultConfig.resolver.sourceExts, 'cjs'],
  },
};

module.exports = mergeConfig(defaultConfig, config);
