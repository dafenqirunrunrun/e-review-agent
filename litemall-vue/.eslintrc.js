module.exports = {
  root: true,
  env: {
    node: true,
    es6: true
  },
  // extends: ['plugin:vue/essential', '@vue/prettier'],
  // rules: {
  //   camelcase: 'off',
  //   quotes: ['error', 'single'],
  //   indent: ['error', 2, { SwitchCase: 1 }],
  //   'no-console': process.env.NODE_ENV === 'production' ? 'error' : 'off',
  //   'no-debugger': process.env.NODE_ENV === 'production' ? 'error' : 'off'
  // },
  parser: 'vue-eslint-parser',
  parserOptions: {
    parser: 'babel-eslint',
    ecmaVersion: 2020,
    sourceType: 'module'
  }
};
