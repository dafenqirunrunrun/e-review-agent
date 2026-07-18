<template>
  <div class="order_detail">
    <div class="order-goods">
      <van-card v-for="item in orderGoods"
                :key="item.id"
                :title="item.goodsName"
                desc="暂无描述"
                :num="item.number"
                :price="item.price +'.00'"
                :thumb="item.picUrl"></van-card>

      <van-cell-group>
        <van-cell title="商品金额">
          <span class="red">{{priceCents(orderInfo.goodsPrice) | yuan}}</span>
        </van-cell>
        <van-cell title="快递费用">
          <span class="red">{{priceCents(orderInfo.freightPrice) | yuan}}</span>
        </van-cell>
      </van-cell-group>
    </div>

    <van-cell-group style="margin-top: 20px;">
      <van-cell icon="dingwei"
                :title="`${orderInfo.consignee}  ${orderInfo.mobile}`"
                :label="orderInfo.address" />
    </van-cell-group>

    <van-cell-group style="margin-top: 20px;">
      <van-cell title="下单时间">
        <span>{{orderInfo.addTime }}</span>
      </van-cell>
      <van-cell title="订单编号">
        <span>{{orderInfo.orderSn }}</span>
      </van-cell>
      <van-cell title="订单备注">
        <span>{{orderInfo.remark }}</span>
      </van-cell>

      <van-cell title="实付款：">
        <span class="red">{{priceCents(orderInfo.actualPrice) | yuan}}</span>
      </van-cell>
      <van-cell title="演示说明">
        <span class="demo_hint">演示支付和演示发货不调用真实外部服务，确认收货后可发布评价进入后台智能治理流程。</span>
      </van-cell>
      <!-- 订单动作 -->
      <van-cell>
        <van-button size="small"
                    v-if="handleOption.cancel"
                    @click="cancelOrder(orderInfo.id)"
                    style=" float:right"
                    round
                    type="danger">取消订单</van-button>
        <van-button size="small"
                    v-if="handleOption.pay"
                    @click="payOrder(orderInfo.id)"
                    style=" float:right"
                    round
                    type="danger">去支付</van-button>
        <van-button size="small"
                    v-if="handleOption.delete"
                    @click="deleteOrder(orderInfo.id)"
                    style=" float:right"
                    type="danger">删除订单</van-button>
        <van-button size="small"
                    v-if="handleOption.confirm"
                    @click="confirmOrder(orderInfo.id)"
                    style=" float:right"
                    type="danger">确认收货</van-button>
        <van-button size="small"
                    v-if="handleOption.comment"
                    @click="commentOrder(orderInfo.id)"
                    style=" float:right"
                    type="warning">去评价</van-button>
        <van-button size="small"
                    v-if="handleOption.refund"
                    @click="refundOrder(orderInfo.id)"
                    style=" float:right"
                    type="danger">退款</van-button>
      </van-cell>
    </van-cell-group>

    <van-cell-group v-if="showExp()"
                    style="margin-top: 20px;">
      <van-cell title="快递公司">
        <span>{{orderInfo.expCode }}</span>
      </van-cell>
      <van-cell title="快递编号">
        <span>{{orderInfo.expNo }}</span>
      </van-cell>
    </van-cell-group>
  </div>
</template>

<script>
import { Card, Field, SubmitBar, Button, Cell, CellGroup, Dialog } from 'vant';
import _ from 'lodash';
import {
  orderDetail,
  orderDelete,
  orderConfirm,
  orderCancel,
  orderRefund
} from '@/api/api';

export default {
  data() {
    return {
      isSubmit: false,
      isDisabled: false,
      orderInfo: {},
      orderGoods: [],
      handleOption: {},
      expressInfo: {}
    };
  },
  created() {
    this.init();
  },

  methods: {
    showExp() {
      return _.has(this.orderInfo, 'expNo');
    },
    deleteOrder(id) {
      let that = this;
      this.$dialog
        .confirm({ message: '确定要删除该订单吗?' })
        .then(() => {
          orderDelete({ orderId: id }).then(() => {
            this.$toast('已删除订单');
            this.$router.go(-1);
          });
        })
        .catch(() => {});
    },
    cancelOrder(id) {
      this.$dialog
        .confirm({ message: '确定要取消该订单吗?' })
        .then(() => {
          orderDelete({ orderId: id }).then(() => {
            this.init();
            this.$toast('已取消该订单');
          });
        })
        .catch(() => {});
    },
    confirmOrder(id) {
      this.$dialog
        .confirm({
          message: '请确认收到货物，确认收货后可进入评价环节，且无法撤销。'
        })
        .then(() => {
          orderConfirm({ orderId: id }).then(() => {
            this.init();
            this.$toast('已确认收货');
          });
        })
        .catch(() => {});
    },
    refundOrder(id) {
      this.$dialog
        .confirm({ message: '确定要申请退款吗?' })
        .then(() => {
          orderRefund({ orderId: id }).then(() => {
            this.init();
            this.$toast('已申请订单退款');
          });
        })
        .catch(() => {});
    },
    commentOrder(id) {
      if (!this.orderGoods || !this.orderGoods.length) {
        this.$toast('该订单暂无可评价商品');
        return;
      }
      this.$router.push({
        path: '/order/comment',
        query: {
          orderId: id,
          orderGoodsId: this.orderGoods[0].id
        }
      });
    },
    payOrder(id) {
      this.toPay(id);
    },
    toPay(id) {
      this.$router.push({ name: 'payment', params: { orderId: id } });
    },
    priceCents(value) {
      const price = Number(value || 0);
      return Number.isFinite(price) ? price * 100 : 0;
    },
    init() {
      let orderId = this.$route.query.orderId;
      orderDetail({ orderId: orderId }).then(res => {
        var data = res.data.data;
        this.orderInfo = data.orderInfo;
        this.orderGoods = data.orderGoods;
        this.handleOption = data.orderInfo.handleOption;
        this.expressInfo = data.expressInfo;
      });
    }
  },

  components: {
    [Dialog.name]: Dialog,
    [CellGroup.name]: CellGroup,
    [Cell.name]: Cell,
    [Button.name]: Button,
    [SubmitBar.name]: SubmitBar,
    [Card.name]: Card,
    [Field.name]: Field
  }
};
</script>


<style lang="scss" scoped>
.order_detail {
  padding-bottom: 70px;
}

.demo_hint {
  display: inline-block;
  color: #6b4a00;
  font-size: 12px;
  line-height: 1.5;
}
</style>
