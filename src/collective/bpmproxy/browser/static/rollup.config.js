import alias from "@rollup/plugin-alias";
import commonjs from "@rollup/plugin-commonjs";
import css from 'rollup-plugin-import-css';
import image from "@rollup/plugin-image";
import json from "@rollup/plugin-json";
import replace from "@rollup/plugin-replace";
import resolve from "@rollup/plugin-node-resolve";
import typescript from "@rollup/plugin-typescript";

const plugins = [
  replace({
    "process.env.NODE_ENV": JSON.stringify("production"),
    "preventAssignment": true,
  }),
  alias({
    entries: [{ find: "inherits", replacement: "inherits/inherits_browser" }],
  }),
  resolve(),
  commonjs({
    include: "node_modules/**",
  }),
  typescript(),
  image(),
  json(),
  css(),
];

export default [
  {
    onwarn: function(warning, superOnWarn) {
      if (warning.code === 'THIS_IS_UNDEFINED') { return; }
      superOnWarn(warning);
    },
    input: "src/index.ts",
    output: {
      file: "bundle.js",
      format: "iife"
    },
    plugins,
  }
];
