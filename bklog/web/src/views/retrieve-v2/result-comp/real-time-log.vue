<!--
* Tencent is pleased to support the open source community by making
* 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
*
* Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
*
* 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
*
* License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
*
* ---------------------------------------------------
* Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
* documentation files (the "Software"), to deal in the Software without restriction, including without limitation
* the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
* to permit persons to whom the Software is furnished to do so, subject to the following conditions:
*
* The above copyright notice and this permission notice shall be included in all copies or substantial portions of
* the Software.
*
* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
* THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
* AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
* CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
* IN THE SOFTWARE.
-->

<template>
  <section
    :class="{
      'log-dialog-wrapper': true,
      'log-full-dialog-wrapper': isScreenFull,
      'log-full-width': !isScreenFull,
    }"
  >
    <div class="dialog-label">
      <span class="dialog-title">{{ title }}</span>
      <template v-if="!targetFields.length">
        <!-- IP -->
        <span style="margin-right: 10px">IP: {{ params.ip || params.serverIp }}</span>
        <!-- 日志路径 -->
        <span
          class="title-overflow"
          v-bk-overflow-tips
        >
          {{ $t('日志路径') + ': ' + (params.path || params.logfile) }}
        </span>
      </template>
      <template v-else>
        <span
          class="title-overflow"
          v-bk-tooltips.bottom="getTargetFieldsStr"
        >
          <span
            v-for="(item, index) of targetFields"
            style="margin-right: 10px"
            :key="index"
          >
            <span>{{ item }}: </span>
            <span>{{ rowShowParams[item] || '/' }}</span>
          </span>
        </span>
      </template>
    </div>
    <div class="dialog-bars">
      <data-filter
        :is-screen-full="isScreenFull"
        @handle-filter="handleFilter"
      />
      <!-- 暂停、复制、全屏 -->
      <div :class="['dialog-bar controls', { 'not-fill': !isScreenFull }]">
        <div
          class="control-icon"
          v-bk-tooltips.top="{ content: isPolling ? $t('暂停') : $t('启动'), delay: 300 }"
          @click="togglePolling"
        >
          <span
            v-if="isPolling"
            class="icon bklog-icon bklog-stop-log"
          ></span>
          <span
            v-else
            class="icon bklog-icon bklog-play-log"
          ></span>
        </div>
        <div
          class="control-icon"
          v-bk-tooltips.top="{ content: $t('复制'), delay: 300 }"
          @click="copyLogText"
        >
          <span class="icon bklog-icon bklog-copy"></span>
        </div>
        <div
          class="control-icon"
          v-bk-tooltips.top="{ content: $t('全屏'), delay: 300 }"
          @click="toggleScreenFull"
        >
          <span class="icon bklog-icon bklog-full-screen-log"></span>
        </div>
      </div>
    </div>
    <div
      ref="realTimeLog"
      class="dialog-log-markdown"
      tabindex="0"
    >
      <log-view
        :filter-key="activeFilterKey"
        :filter-type="filterType"
        :ignore-case="ignoreCase"
        :interval="interval"
        :is-real-time-log="true"
        :log-list="logList"
        :reverse-log-list="reverseLogList"
        :max-length="maxLength"
        :shift-length="shiftLength"
        :light-list="highlightList"
        :show-type="showType"
      />
    </div>
    <log-view-control
      :show-type="showType"
      :light-list="highlightList"
    />
    <p class="handle-tips">{{ $t('快捷键  Esc:退出; PageUp: 向上翻页; PageDn: 向下翻页') }}</p>
  </section>
</template>

<script>
  import { getFlatObjValues } from '@/common/util';
  import logView from '@/components/log-view';
  import logViewControl from '@/components/log-view/log-view-control';

  import DataFilter from '../condition-comp/data-filter';

  export default {
    name: 'RealTimeLog',
    components: {
      logView,
      logViewControl,
      DataFilter,
    },
    props: {
      logParams: {
        type: Object,
        default() {
          return {};
        },
      },
      title: {
        type: String,
        require: true,
      },
      targetFields: {
        type: Array,
        default: () => [],
      },
      indexSetId: {
        type: Number,
        default: 0,
      },
    },
    data() {
      return {
        filterType: 'include',
        activeFilterKey: '',
        params: {},
        isScreenFull: true,
        loading: false, // 是否已经发出请求
        isPolling: false,
        timer: null,
        cloudAreaList: [],
        logList: [],
        reverseLogList: [],
        // 日志最大长度
        maxLength: Number(window.REAL_TIME_LOG_MAX_LENGTH) || 20000,
        // 超过此长度删除部分日志
        shiftLength: Number(window.REAL_TIME_LOG_SHIFT_LENGTH) || 10000,
        isScrollBottom: true,
        logWrapperEl: null,
        zero: true,
        ignoreCase: false,
        flipScreen: '',
        flipScreenList: [],
        interval: {
          prev: 0,
          next: 0,
        },
        showType: 'log',
        highlightList: [],
        rowShowParams: {},
        throttleTimer: null,
        isInit: true,
      };
    },
    computed: {
      getTargetFieldsStr() {
        return this.targetFields.reduce((acc, cur) => {
          acc += `${cur}: ${this.rowShowParams[cur] || '/ '} `;
          return acc;
        }, '');
      },
    },
    created() {
      this.deepClone(this.logParams);
    },
    mounted() {
      document.addEventListener('keyup', this.handleKeyup);
      this.requestRealTimeLog();
      this.togglePolling();
      this.registerScrollEvent();
    },
    beforeDestroy() {
      document.removeEventListener('keyup', this.handleKeyup);

      this.timer && clearInterval(this.timer);
    },
    methods: {
      handleKeyup(event) {
        if (event.keyCode === 27) {
          this.$emit('close-dialog');
        }
      },
      deepClone(obj) {
        const string = JSON.stringify(obj)
          .replace(/<mark>/g, '')
          .replace(/<\/mark>/g, '');
        // 扁平化对象内的对象值
        const parseObj = JSON.parse(string);
        if (this.targetFields.length) {
          const { newObject } = getFlatObjValues(parseObj);
          this.rowShowParams = newObject;
        }
        this.params = parseObj;
      },
      requestRealTimeLog() {
        if (this.loading) {
          return false;
        }
        this.loading = true;
        this.$http
          .request('retrieve/getRealTimeLog', {
            params: {
              index_set_id: this.indexSetId,
            },
            data: Object.assign(
              { order: '-', size: 50, zero: this.zero, dtEventTimeStamp: this.logParams.dtEventTimeStamp },
              this.params,
            ),
          })
          .then(res => {
            // 通过gseindex 去掉出返回日志， 并加入现有日志
            const { list } = res.data;
            if (list && list.length) {
              // 超过最大长度时剔除部分日志
              if (this.logList.length > this.maxLength) {
                this.logList.splice(0, this.shiftLength);
                this.logWrapperEl.scrollTo({ top: 0 });
              }

              const logArr = [];
              list.forEach(item => {
                const { log } = item;
                logArr.push({ log });
              });
              this.deepClone(list[list.length - 1]);
              if (this.isInit) {
                this.reverseLogList = logArr.slice(0, -1);
                this.logList = logArr.slice(-1);
              } else {
                this.logList.splice(this.logList.length, 0, ...logArr);
              }
              if (this.isScrollBottom) {
                this.$nextTick(() => {
                  if (this.zero) {
                    // 首次不要滚动动画
                    this.logWrapperEl.scrollTo({ top: this.logWrapperEl.scrollHeight });
                    this.zero = false;
                  } else {
                    this.$easeScroll(
                      this.logWrapperEl.scrollHeight - this.logWrapperEl.offsetHeight,
                      300,
                      this.logWrapperEl,
                    );
                  }
                });
              }
            }
          })
          .finally(() => {
            this.isInit = false;
            setTimeout(() => {
              this.loading = false;
            }, 300);
          });
      },
      clearLogList() {
        if (this.isPolling) {
          this.timer && clearInterval(this.timer);
        }
        this.logList.splice(0, this.logList.length);
        if (this.isPolling) {
          this.isPolling = false;
          this.requestRealTimeLog();
          this.togglePolling();
        }
      },
      togglePolling() {
        this.isPolling = !this.isPolling;
        this.timer && clearInterval(this.timer);
        if (this.isPolling) {
          this.timer = setInterval(this.requestRealTimeLog, 5000);
        }
      },
      toggleScreenFull() {
        this.isScreenFull = !this.isScreenFull;
        this.$emit('toggle-screen-full', this.isScreenFull);
      },
      registerScrollEvent() {
        this.logWrapperEl = document.querySelector('.dialog-log-markdown');
        this.logWrapperEl.addEventListener('scroll', () => {
          const { scrollTop } = this.logWrapperEl;
          const contentHeight = this.logWrapperEl.scrollHeight;
          const { offsetHeight } = this.logWrapperEl;
          if (scrollTop + offsetHeight >= contentHeight) {
            this.isScrollBottom = true;
          } else {
            this.isScrollBottom = false;
          }
        });
      },
      copyLogText() {
        const el = document.createElement('textarea');
        const copyStrList = this.reverseLogList.concat(this.logList).map(item => item.log);
        el.value = copyStrList.join('\n');
        el.setAttribute('readonly', '');
        el.style.position = 'absolute';
        el.style.left = '-9999px';
        document.body.appendChild(el);
        const selected = document.getSelection().rangeCount > 0 ? document.getSelection().getRangeAt(0) : false;
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
        if (selected) {
          document.getSelection().removeAllRanges();
          document.getSelection().addRange(selected);
        }
        this.$bkMessage({
          theme: 'success',
          message: this.$t('复制成功'),
        });
      },
      filterLog(value) {
        this.activeFilterKey = value;
        clearTimeout(this.throttleTimer);
        this.throttleTimer = setTimeout(() => {
          if (!value) {
            this.$nextTick(() => {
              this.initLogScrollPosition();
            });
          }
        }, 300);
      },
      initLogScrollPosition() {
        // 确定第0条的位置
        this.firstLogEl = document.querySelector('.dialog-log-markdown .log-init');
        // 没有数据
        if (!this.firstLogEl) return;
        const logContentHeight = this.firstLogEl.scrollHeight;
        const logOffsetTop = this.firstLogEl.offsetTop;

        const wrapperOffsetHeight = this.$refs.realTimeLog.offsetHeight;

        if (wrapperOffsetHeight <= logContentHeight) {
          this.$refs.realTimeLog.scrollTop = logOffsetTop;
        } else {
          this.$refs.realTimeLog.scrollTop = logOffsetTop - Math.ceil((wrapperOffsetHeight - logContentHeight) / 2);
        }
        // 避免重复请求
        setTimeout(() => {
          this.$refs.realTimeLog.addEventListener('scroll', this.handleScroll, { passive: true });
        }, 64);
      },
      handleFilter(field, value) {
        if (field === 'filterKey') {
          this.filterLog(value);
        } else {
          this[field] = value;
        }
      },
    },
  };
</script>

<style lang="scss">
  @import '../../../scss/mixins/clearfix.scss';
  @import '../../../scss/mixins/scroller';

  .log-dialog.bk-dialog-wrapper {
    .bk-dialog-header {
      padding-bottom: 12px;
      line-height: 30px;
    }

    .bk-dialog-body {
      padding-bottom: 10px;
    }
  }

  .log-dialog-wrapper {
    .dialog-label {
      display: flex;
      align-items: center;
      height: 30px;
      margin-bottom: 20px;
      overflow: hidden;
      white-space: nowrap;
    }

    .dialog-title {
      margin-right: 20px;
      font-size: 20px;
      line-height: 20px;
      color: #313238;
    }

    .dialog-bars {
      position: relative;
      display: flex;
      align-items: start;
      justify-content: space-between;

      .dialog-bar {
        display: flex;
        align-items: center;

        .label-text {
          margin-right: 10px;
          color: #2d3542;
        }

        .hot-key {
          color: #979ba5;
        }

        &.controls {
          flex: 1;

          .control-icon {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            font-size: 32px;
            cursor: pointer;
            border: 1px solid #c4c6cc;
            transition: color 0.2s;

            &:not(:last-child) {
              margin-right: 10px;
            }

            &:hover {
              color: #3a84ff;
              transition: color 0.2s;
            }
          }

          &.not-fill .control-icon:not(:last-child) {
            margin-right: 4px;
          }
        }
      }
    }

    .dialog-log-markdown {
      height: 404px;
      overflow-y: auto;
      background: #f5f7fa;
      border: 1px solid #dcdee5;
      border-bottom: none;

      @include scroller($backgroundColor: #aaa, $width: 4px);

      &::-webkit-scrollbar {
        background-color: #dedede;
      }
    }

    .handle-tips {
      margin-top: 10px;
      color: #63656e;
    }

    &.log-full-dialog-wrapper {
      height: calc(100% - 16px);
      margin-top: 10px;
      overflow: hidden;

      .dialog-log-markdown {
        height: calc(100% - 176px);
      }

      .handle-tips {
        margin-top: 18px;
      }
    }
  }

  .log-full-width {
    width: 1030px;
  }
</style>
