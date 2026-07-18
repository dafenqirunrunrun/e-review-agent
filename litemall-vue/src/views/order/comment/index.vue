<template>
  <div class="order_comment">
    <van-cell-group v-if="goods" class="goods_card">
      <van-card
        :title="goods.goodsName"
        :desc="goods.goodsSn"
        :thumb="goods.picUrl"
        :num="goods.number"
        :price="goods.price"
      />
    </van-cell-group>

    <van-cell-group title="评价信息">
      <van-cell title="评分">
        <van-rate v-model="form.star" />
      </van-cell>
      <van-field
        v-model="form.content"
        type="textarea"
        rows="5"
        autosize
        label="评价内容"
        placeholder="请输入真实商品评价，建议包含体验、问题或售后诉求"
      />
      <van-field
        v-model="imageUrl"
        label="图片 URL"
        placeholder="可选，输入图片链接用于图文评价演示"
        clearable
      />
    </van-cell-group>

    <div v-if="imageUrl" class="image_preview">
      <img :src="imageUrl" alt="评价图片预览">
    </div>

    <div class="ai_hint">
      提交后将写入真实商品评价记录，后台智能体可自动巡检分析。若当前页面缺少订单上下文，请从订单列表的“去评价”入口进入。
    </div>

    <van-button class="submit_btn" :loading="submitting" type="danger" @click="submitComment">
      提交评价
    </van-button>
  </div>
</template>

<script>
import { orderGoods, orderComment } from '@/api/api';
import { Card, Dialog, Field, Rate } from 'vant';
import _ from 'lodash';

export default {
  name: 'order-comment',
  data() {
    return {
      orderGoodsId: null,
      goods: null,
      imageUrl: '',
      submitting: false,
      form: {
        star: 5,
        content: ''
      }
    };
  },
  created() {
    this.orderGoodsId = Number(this.$route.query.orderGoodsId);
    this.getGoods();
  },
  methods: {
    getGoods() {
      if (!this.orderGoodsId) {
        this.$toast('缺少订单商品 ID，请从订单列表进入评价页');
        return;
      }
      orderGoods({ ogid: this.orderGoodsId }).then(res => {
        this.goods = res.data.data;
      });
    },
    submitComment() {
      if (!this.form.content || this.form.content.trim().length < 3) {
        this.$toast('请填写至少 3 个字的评价内容');
        return;
      }
      const picUrls = this.imageUrl ? [this.imageUrl] : [];
      this.submitting = true;
      orderComment({
        orderGoodsId: this.orderGoodsId,
        content: this.form.content.trim(),
        star: this.form.star,
        hasPicture: picUrls.length > 0,
        picUrls
      })
        .then(() => {
          this.$toast('评价提交成功，后台智能体将自动巡检分析');
          this.$router.replace({ path: '/user/order/list/4' });
        })
        .catch(err => {
          const message = _.get(err, 'data.errmsg') || _.get(err, 'response.data.errmsg') || '评价提交失败';
          Dialog.alert({ message });
        })
        .finally(() => {
          this.submitting = false;
        });
    }
  },
  components: {
    [Card.name]: Card,
    [Field.name]: Field,
    [Rate.name]: Rate,
    [Dialog.name]: Dialog
  }
};
</script>

<style lang="scss" scoped>
.order_comment {
  padding-bottom: 80px;
  background: #f7f8fa;
  min-height: 100vh;
}

.goods_card {
  margin-bottom: 10px;
}

.image_preview {
  margin: 12px 15px;
  padding: 12px;
  background: #fff;
  border-radius: 4px;

  img {
    display: block;
    max-width: 100%;
    border-radius: 4px;
  }
}

.ai_hint {
  margin: 12px 15px;
  color: #666;
  font-size: 13px;
  line-height: 1.5;
}

.submit_btn {
  position: fixed;
  left: 0;
  bottom: 0;
  width: 100%;
}
</style>
