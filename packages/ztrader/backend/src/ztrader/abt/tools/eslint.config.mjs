
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import globals from "globals";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    ignores: [".next/", "node_modules/", "dist/", "build/", "coverage/", "out/", ".turbo/"],
  },
  {
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      "@typescript-eslint/no-unused-vars": "off",
      "no-undef": "off",
      "no-empty": "off",
      "@typescript-eslint/ban-ts-comment": "off",
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-require-imports": "off",
      "@typescript-eslint/no-var-requires": "off",
      "no-useless-escape": "off",
      "no-fallthrough": "off",
      "no-control-regex": "off",
      "react-hooks/exhaustive-deps": "off",
      "@typescript-eslint/triple-slash-reference": "off"
    }
  }
);
