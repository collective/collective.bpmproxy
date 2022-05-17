import alias from "@rollup/plugin-alias";
import commonjs from "@rollup/plugin-commonjs";
import image from "@rollup/plugin-image";
import json from "@rollup/plugin-json";
import replace from "@rollup/plugin-replace";
import resolve from "@rollup/plugin-node-resolve";

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
  image(),
  json()
];

export default [
  {
    onwarn: function(warning, superOnWarn) {
      if (warning.code === 'THIS_IS_UNDEFINED') { return; }
      superOnWarn(warning);
    },
    input: "src/bpmproxy.js",
    output: {
      file: "bpmproxy.js",
    },
    plugins,
  },
];
