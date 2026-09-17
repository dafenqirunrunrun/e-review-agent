<template>
  <div class="payment">
    <div class="time_down payment_group">
      请在
      <span class="red">半小时内</span>
      完成付款，否则系统自动取消订单
    </div>

    <van-cell-group class="payment_group">
      <van-cell title="订单编号" :value="order.orderInfo.orderSn"/>
      <van-cell title="实付金额">
        <span class="red">{{actualPriceCents | yuan}}</span>
      </van-cell>
    </van-cell-group>

    <div class="pay_way_group">
      <div class="pay_way_title">选择支付方式</div>
      <van-radio-group v-model="payWay">
        <van-cell-group>
          <van-cell>
            <template slot="title">
              <img src="../../../assets/images/ali_pay.png" alt="支付宝" width="82" height="29">
            </template>
            <van-radio name="ali"/>
          </van-cell>
          <van-cell>
            <template slot="title">
              <img src="../../../assets/images/wx_pay.png" alt="微信支付" width="113" height="23">
            </template>            
            <van-radio name="wx"/>
          </van-cell>
        </van-cell-group>
      </van-radio-group>
    </div>

    <div class="demo_pay_hint">
      {{ demoStatus.message || '答辩演示模式：不调用真实支付，仅推进订单状态。' }}
    </div>
    <van-button
      v-if="demoPaymentAvailable"
      class="demo_pay_submit"
      :loading="demoPayLoading"
      :disabled="!hasOrderContext"
      @click="demoPay"
      type="danger">演示支付成功（不调用真实支付）</van-button>
    <div v-if="!hasOrderContext" class="demo_pay_disabled">请从订单提交或订单列表进入支付页后再执行演示支付。</div>
    <div v-else-if="!demoPaymentAvailable" class="demo_pay_disabled">当前未开启演示支付模式。</div>
    <van-button class="pay_submit" @click="pay" type="primary" bottomAction>去支付</van-button>
  </div>
</template>

<script>
import { Radio, RadioGroup, Dialog } from 'vant';
import { aiDemoStatus, orderDetail, orderPrepay, orderH5pay, orderMockPay } from '@/api/api';
import _ from 'lodash';
import { getLocalStorage, setLocalStorage } from '@/utils/local-storage';

export default {
  name: 'payment',

  data() {
    return {
      payWay: 'wx',
      order: {
        orderInfo: {},
        orderGoods: []
      },
      orderId: 0,
      demoPayLoading: false,
      demoStatus: {
        demoModeEnabled: true,
        demoPaymentEnabled: true,
        message: '答辩演示模式：不调用真实支付，仅推进订单状态。'
      }
    };
  },
  created() {
    this.loadDemoStatus();
    if (_.has(this.$route.params, 'orderId')) {
      this.orderId = this.$route.params.orderId;
      this.getOrder(this.orderId);
    }
  },
  computed: {
    actualPriceCents() {
      const price = Number(_.get(this.order, 'orderInfo.actualPrice', 0));
      return Number.isFinite(price) ? price * 100 : 0;
    },
    hasOrderContext() {
      return Number(this.orderId) > 0;
    },
    demoPaymentAvailable() {
      return this.demoStatus.demoModeEnabled !== false && this.demoStatus.demoPaymentEnabled !== false;
    }
  },
  methods: {
    loadDemoStatus() {
      aiDemoStatus()
        .then(res => {
          this.demoStatus = res.data.data || this.demoStatus;
        })
        .catch(() => {
          this.demoStatus.message = 'AI 演示状态接口暂不可用，页面保留本地演示支付入口。';
        });
    },
    getOrder(orderId) {
      orderDetail({orderId: orderId}).then(res => {
        this.order = res.data.data;
      });
    },
    demoPay() {
      if (!this.hasOrderContext) {
        Dialog.alert({ message: '请从订单提交或订单列表进入支付页后再执行演示支付。' });
        return;
      }
      this.demoPayLoading = true;
      orderMockPay({ orderId: this.orderId })
        .then(() => {
          this.$toast('演示支付成功');
          this.$router.replace({ path: '/user/order/list/2' });
        })
        .catch(err => {
          const message = _.get(err, 'data.errmsg') || _.get(err, 'response.data.errmsg') || '演示支付失败';
          Dialog.alert({ message });
        })
        .finally(() => {
          this.demoPayLoading = false;
        });
    },
    pay() {
      
      Dialog.alert({
        message: '你选择了' + (this.payWay === 'wx' ? '微信支付' : '支付宝支付')
      }).then(() => {
        if (this.payWay === 'wx') {
          let ua = navigator.userAgent.toLowerCase();
          let isWeixin = ua.indexOf('micromessenger') != -1;
          if (isWeixin) {
            orderPrepay({ orderId: this.orderId })
              .then(res => {
                let data = res.data.data;
                let prepay_data = JSON.stringify({
                  appId: data.appId,
                  timeStamp: data.timeStamp,
                  nonceStr: data.nonceStr,
                  package: data.packageValue,
                  signType: 'MD5',
                  paySign: data.paySign
                });
                setLocalStorage({ prepay_data: prepay_data });

                if (typeof WeixinJSBridge == 'undefined') {
                  if (document.addEventListener) {
                    document.addEventListener(
                      'WeixinJSBridgeReady',
                      this.onBridgeReady,
                      false
                    );
                  } else if (document.attachEvent) {
                    document.attachEvent(
                      'WeixinJSBridgeReady',
                      this.onBridgeReady
                    );
                    document.attachEvent(
                      'onWeixinJSBridgeReady',
                      this.onBridgeReady
                    );
                  }
                } else {
                  this.onBridgeReady();
                }
              })
              .catch(err => {
                Dialog.alert({ message: err.data.errmsg });
                that.$router.replace({
                  name: 'paymentStatus',
                  params: {
                    status: 'failed'
                  }
                });
              });
          } else {
            orderH5pay({ orderId: this.orderId })
              .then(res => {
                let data = res.data.data;
                window.location.replace(
                  data.mwebUrl +
                  '&redirect_url=' +
                  encodeURIComponent(
                    window.location.origin +
                    '/#/?orderId=' +
                    this.orderId +
                    '&tip=yes'
                  )
                );
              })
              .catch(err => {
                Dialog.alert({ message: err.data.errmsg });
              });
          }
        } else {
          //todo : alipay
        }
      });
    },
    onBridgeReady() {
      let that = this;
      let data = getLocalStorage('prepay_data');
      // eslint-disable-next-line no-undef
      WeixinJSBridge.invoke(
        'getBrandWCPayRequest',
        JSON.parse(data.prepay_data),
        function(res) {
          if (res.err_msg == 'get_brand_wcpay_request:ok') {
            that.$router.replace({
              name: 'paymentStatus',
              params: {
                status: 'success'
              }
            });
          } else if (res.err_msg == 'get_brand_wcpay_request:cancel') {
            that.$router.replace({
              name: 'paymentStatus',
              params: {
                status: 'cancel'
              }
            });
          } else {
            that.$router.replace({
              name: 'paymentStatus',
              params: {
                status: 'failed'
              }
            });
          }
        }
      );
    }
  },

  components: {
    [Radio.name]: Radio,
    [RadioGroup.name]: RadioGroup,
    [Dialog.name]: Dialog
  }
};
</script>

<style lang="scss" scoped>
.payment_group {
  margin-bottom: 10px;
}

.time_down {
  background-color: #fffeec;
  padding: 10px 15px;
}

.pay_submit {
  position: fixed;
  bottom: 0;
  width: 100%;
}

.demo_pay_hint {
  margin: 12px 15px 8px;
  color: #666;
  font-size: 13px;
  line-height: 1.5;
}

.demo_pay_submit {
  margin: 0 15px 58px;
  width: calc(100% - 30px);
}

.demo_pay_disabled {
  margin: 0 15px 58px;
  padding: 10px;
  color: #999;
  background: #f7f8fa;
  border-radius: 4px;
  text-align: center;
}

.pay_way_group img {
  vertical-align: middle;
}

.pay_way_title {
  padding: 15px;
  background-color: #fff;
}
</style>
