const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);

config.watchFolders = [
  "C:\\nm\\node_modules"
];

config.resolver.nodeModulesPaths = [
  "C:\\nm\\node_modules",
  "./node_modules"
];

module.exports = config;