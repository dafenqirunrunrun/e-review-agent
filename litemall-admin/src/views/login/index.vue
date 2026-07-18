<template>
  <div class="login-container">
    <div class="locale-changer">
      <locale-changer />
    </div>
    <el-form ref="loginForm" :model="loginForm" :rules="loginRules" class="login-form" auto-complete="on" label-position="left">
      <div class="title-container">
        <h3 class="title">{{ $t('login.page.title') }}</h3>
        <p class="subtitle">鐢靛晢鍥炬枃璇勮鏅鸿兘娌荤悊绯荤粺</p>
      </div>

      <el-form-item prop="username">
        <span class="svg-container">
          <svg-icon icon-class="user" />
        </span>
        <el-input v-model="loginForm.username" name="username" type="text" tabindex="1" auto-complete="on" :placeholder="$t('login.placeholder.username')" />
      </el-form-item>

      <el-form-item prop="password">
        <span class="svg-container">
          <svg-icon icon-class="password" />
        </span>
        <el-input v-model="loginForm.password" :type="passwordType" name="password" auto-complete="on" tabindex="2" show-password :placeholder="$t('login.placeholder.password')" @keyup.enter.native="handleLogin" />
      </el-form-item>

      <el-button :loading="loading" type="primary" style="width:100%;margin-bottom:30px;" @click.native.prevent="handleLogin">{{ $t('login.button.login') }}</el-button>

      <div class="tips-panel">
        <div class="tips">
          <span>Use your local demo admin account.</span>
          <span>Do not commit real passwords.</span>
        </div>
        <div class="tips">
          <span>婕旂ず閲嶇偣锛欰gent 宸℃銆侀闄╂不鐞嗐€佽繍钀ラ棴鐜€丄gent Trace銆丄gent Eval</span>
        </div>
      </div>
    </el-form>

    <div class="copyright">
      E-Review Agent 姣曚笟璁捐婕旂ず绯荤粺 路 鍩轰簬寮€婧愮數鍟嗙郴缁熶簩娆″紑鍙?
    </div>
  </div>
</template>

<script>
import { getKaptcha } from '@/api/login'
import LocaleChanger from '@/components/LocaleChanger'

export default {
  name: 'Login',
  components: { LocaleChanger },
  data() {
    const validatePassword = (rule, value, callback) => {
      if (value.length < 6) {
        callback(new Error('Password length should be greater than 6'))
      } else {
        callback()
      }
    }
    return {
      loginForm: {
        username: '',
        password: '',
        code: ''
      },
      codeImg: '',
      loginRules: {
        username: [{ required: true, message: 'Username is required', trigger: 'blur' }],
        password: [
          { required: true, message: 'Password is required', trigger: 'blur' },
          { validator: validatePassword, trigger: 'blur' }
        ]
      },
      passwordType: 'password',
      loading: false
    }
  },
  watch: {
    $route: {
      handler: function(route) {
        this.redirect = route.query && route.query.redirect
      },
      immediate: true
    }
  },
  created() {
    this.getCode()
  },
  methods: {
    getCode() {
      getKaptcha().then(response => {
        this.codeImg = response.data.data
      })
    },
    handleLogin() {
      this.$refs.loginForm.validate(valid => {
        if (valid && !this.loading) {
          this.loading = true
          this.$store.dispatch('LoginByUsername', this.loginForm).then(() => {
            this.loading = false
            this.$router.push({ path: this.redirect || '/' })
          }).catch(response => {
            if (response.data.data) {
              this.codeImg = response.data.data
            }
            this.$notify.error({
              title: '澶辫触',
              message: response.data.errmsg
            })
            this.loading = false
          })
        } else {
          return false
        }
      })
    }
  }
}
</script>

<style lang="scss">
$bg:#283443;
$light_gray:#fff;
$cursor: #fff;

@supports (-webkit-mask: none) and (not (cater-color: $cursor)) {
  .login-container .el-input input {
    color: $cursor;
  }
}

.login-container {
  .el-input {
    display: inline-block;
    height: 47px;
    width: 85%;

    input {
      background: transparent;
      border: 0px;
      -webkit-appearance: none;
      border-radius: 0px;
      padding: 12px 5px 12px 15px;
      color: $light_gray;
      height: 47px;
      caret-color: $cursor;

      &:-webkit-autofill {
        box-shadow: 0 0 0px 1000px $bg inset !important;
        -webkit-text-fill-color: $cursor !important;
      }
    }
  }

  .el-form-item {
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(0, 0, 0, 0.1);
    border-radius: 5px;
    color: #454545;
  }
}
</style>

<style lang="scss" scoped>
$bg:#243142;
$dark_gray:#889aa4;
$light_gray:#eee;

.login-container {
  min-height: 100%;
  width: 100%;
  background: linear-gradient(135deg, #243142 0%, #1f2937 45%, #0f766e 100%);
  overflow: hidden;

  .locale-changer {
    position: absolute;
    top: 16px;
    right: 16px;
  }

  .login-form {
    position: relative;
    width: 520px;
    max-width: 100%;
    padding: 150px 35px 0;
    margin: 0 auto;
    overflow: hidden;
  }

  .tips-panel {
    position: relative;
  }

  .tips {
    font-size: 14px;
    color: #fff;
    margin-bottom: 10px;
    line-height: 1.7;

    span {
      &:first-of-type {
        margin-right: 16px;
      }
    }
  }

  .svg-container {
    padding: 6px 5px 6px 15px;
    color: $dark_gray;
    vertical-align: middle;
    width: 30px;
    display: inline-block;
  }

  .title-container {
    position: relative;

    .title {
      font-size: 28px;
      color: $light_gray;
      margin: 0 auto 10px;
      text-align: center;
      font-weight: bold;
    }

    .subtitle {
      margin: 0 auto 36px;
      color: rgba(255, 255, 255, 0.78);
      text-align: center;
      font-size: 14px;
    }
  }

  .copyright {
    font-size: 12px;
    color: #fff;
    position: absolute;
    bottom: 0;
    left: 50%;
    transform: translate(-50%, -50%);
    margin-bottom: 20px;
    letter-spacing: 0.6px;
    white-space: nowrap;
  }
}
</style>

