import ast
import sys
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import pandas as pd
import math
import streamlit as st


def generate_repayment_schedule(
        loan_amount=400000,
        loan_years=30,
        first_pay_date=datetime(2022, 9, 12),
        initial_rate=0.0325,
        rate_changes=None,
        prepayment_details=None,
        repayment_type="equal_principal"
):
    """
    生成公积金贷款还款计划（支持等额本金/等额本息 + 多笔提前还款 + 动态利率）

    参数：
    - loan_amount: 贷款总金额
    - loan_years: 贷款年限（年）
    - first_pay_date: 首次还款日期（datetime对象）
    - initial_rate: 初始利率
    - rate_changes: 利率变更字典 {datetime: rate}
    - prepayment_details: 提前还款详情列表 [{'date': datetime, 'amount': float}]
    - repayment_type: 还款类型 ["equal_principal", "equal_payment"]
    """

    if rate_changes is None:
        rate_changes = {}
    if prepayment_details is None:
        prepayment_details = []

    # 初始化变量
    current_date = first_pay_date
    remaining_principal = loan_amount
    total_months = loan_years * 12
    schedule = []
    current_rate = initial_rate
    month = 1

    # 计算等额本息月供
    if repayment_type == "equal_payment":
        monthly_rate = initial_rate / 100 / 12
        equal_monthly_payment = loan_amount * (monthly_rate * (1 + monthly_rate) ** total_months) / ((1 + monthly_rate) ** total_months - 1)
    else:
        equal_monthly_payment = 0

    original_monthly_principal = loan_amount / total_months
    monthly_principal = original_monthly_principal

    # 排序提前还款信息
    prepayment_details.sort(key=lambda x: x['date'])

    while remaining_principal > 0 and month <= total_months:
        # 检查利率变更
        current_year_month = datetime(current_date.year, current_date.month, 1)
        for change_date in sorted(rate_changes.keys()):
            # 确保 change_date 是 datetime 类型
            if isinstance(change_date, date) and not isinstance(change_date, datetime):
                change_date_key = datetime.combine(change_date, datetime.min.time())
            else:
                change_date_key = change_date

            if current_date >= change_date_key:  # 使用统一后的 change_date_key 进行比较
                current_rate = rate_changes[change_date]
                print(f"[DEBUG] 生效日: {change_date}, 新利率: {current_rate}")  # 添加调试信息
        monthly_rate = current_rate / 100 / 12

        # # 根据还款类型计算当期还款内容
        # if repayment_type == "equal_principal":
        #     interest = remaining_principal * monthly_rate
        #     principal_payment = monthly_principal
        # elif repayment_type == "equal_payment":
        #     interest = remaining_principal * monthly_rate
        #     principal_payment = equal_monthly_payment - interest
        # else:
        #     raise ValueError("不支持的还款类型")
        #
        # # 添加常规还款记录
        # schedule.append({
        #     '期数': month,
        #     '还款日期': current_date.strftime('%Y-%m-%d'),
        #     '类型': '正常还款',
        #     '月供本金': principal_payment,
        #     '月供利息': interest,
        #     '剩余本金': remaining_principal - principal_payment,
        # })
        #
        # # 更新剩余本金
        # remaining_principal -= principal_payment

        # 检查并处理提前还款
        processed_months = set()  # 记录已经处理过的月份，防止重复处理正常还款

        prepayment_details = [item for item in prepayment_details if datetime.combine(item['date'], datetime.min.time()) >= current_year_month]
        for prepay in prepayment_details:
            if current_date.year == prepay['date'].year and current_date.month == prepay['date'].month:
                if (current_date.year, current_date.month, current_date.day) in processed_months:
                    continue  # 如果该月份已经处理过，跳过重复处理
                prepay_amount = prepay.get('amount', 0)
                if prepay_amount > 0 and remaining_principal > 0:
                    # 确定提前还款日期与当前还款日的关系
                    prepay_date = prepay['date']
                    if isinstance(prepay_date, date) and not isinstance(prepay_date, datetime):
                        prepay_date = datetime.combine(prepay_date, datetime.min.time())

                    # 在每次使用前重新计算 monthly_rate 和其他相关变量
                    monthly_rate = current_rate / 100 / 12

                    # 根据还款类型重新计算当期的还款内容
                    if repayment_type == "equal_principal":
                        interest = remaining_principal * monthly_rate
                        principal_payment = monthly_principal
                    elif repayment_type == "equal_payment":
                        monthly_rate = initial_rate / 100 / 12
                        equal_monthly_payment = loan_amount * (monthly_rate * (1 + monthly_rate) ** total_months) / ((1 + monthly_rate) ** total_months - 1)
                        interest = remaining_principal * monthly_rate
                        principal_payment = equal_monthly_payment - interest
                    else:
                        raise ValueError("不支持的还款类型")

                    # 如果提前还款日在当前还款日之前，先执行提前还款
                    if prepay_date < current_date:
                        # 计算提前还款利息
                        days_in_period = max((prepay_date - current_date).days, 1)
                        daily_interest = (remaining_principal * current_rate / 100) / 365
                        interest_before_prepayment = daily_interest * days_in_period

                        # 执行提前还款
                        remaining_principal -= prepay_amount
                        schedule.append({
                            '期数': month,
                            '还款日期': prepay_date.strftime('%Y-%m-%d'),
                            '类型': '提前还款',
                            '月供本金': prepay_amount,
                            '月供利息': interest_before_prepayment,
                            '剩余本金': remaining_principal,
                        })

                        # 添加常规还款记录
                        schedule.append({
                            '期数': month,
                            '还款日期': current_date.strftime('%Y-%m-%d'),
                            '类型': '正常还款',
                            '月供本金': principal_payment,
                            '月供利息': interest,
                            '剩余本金': remaining_principal - principal_payment,
                        })

                        # 更新剩余本金
                        remaining_principal -= principal_payment

                        # # 更新当期的剩余本金，确保后续计算正确
                        # if len(schedule) > 1:
                        #     prev_record = schedule[-2]
                        #     prev_record['剩余本金'] = remaining_principal + prepay_amount
                        #     # prev_record['月供本金'] -= prepay_amount
                        #     prev_record['月供总额'] = prev_record['月供本金'] + prev_record['月供利息']
                        #     prev_record['累计已还本金'] = loan_amount - prev_record['剩余本金']
                        #     if '累计已还利息' in prev_record:
                        #         prev_record['累计已还利息'] += interest_before_prepayment
                        #     else:
                        #         prev_record['累计已还利息'] = interest_before_prepayment
                    else:
                        # 如果提前还款日在当前还款日之后，先执行正常还款
                        # 添加常规还款记录
                        schedule.append({
                            '期数': month,
                            '还款日期': current_date.strftime('%Y-%m-%d'),
                            '类型': '正常还款',
                            '月供本金': principal_payment,
                            '月供利息': interest,
                            '剩余本金': remaining_principal - principal_payment,
                        })

                        # 更新剩余本金
                        remaining_principal -= principal_payment

                        # 计算提前还款利息
                        days_in_period = max((prepay_date - current_date).days, 1)
                        daily_interest = (remaining_principal * current_rate / 100) / 365
                        interest_before_prepayment = daily_interest * days_in_period

                        # 执行提前还款
                        remaining_principal -= prepay_amount
                        schedule.append({
                            '期数': month,
                            '还款日期': prepay_date.strftime('%Y-%m-%d'),
                            '类型': '提前还款',
                            '月供本金': prepay_amount,
                            '月供利息': interest_before_prepayment,
                            '剩余本金': remaining_principal,
                        })

                        # 更新当期的剩余本金，确保后续计算正确
                        if len(schedule) > 1:
                            prev_record = schedule[-2]
                            prev_record['剩余本金'] = remaining_principal + prepay_amount
                            prev_record['月供本金'] -= prepay_amount
                            prev_record['月供总额'] = prev_record['月供本金'] + prev_record['月供利息']
                            prev_record['累计已还本金'] = loan_amount - prev_record['剩余本金']
                            if '累计已还利息' in prev_record:
                                prev_record['累计已还利息'] += interest_before_prepayment
                            else:
                                prev_record['累计已还利息'] = interest_before_prepayment

                        # 避免重复添加正常还款记录
                        processed_months.add((current_date.year, current_date.month, current_date.day))
                        continue

                    # 标记该月份已经处理
                    processed_months.add((current_date.year, current_date.month, current_date.day))
            else:
                if (current_date.year, current_date.month, current_date.day) in processed_months:
                    continue  # 如果该月份已经处理过，跳过重复处理
                # # 确定提前还款日期与当前还款日的关系
                # prepay_date = prepay['date']
                # if isinstance(prepay_date, date) and not isinstance(prepay_date, datetime):
                #     prepay_date = datetime.combine(prepay_date, datetime.min.time())

                # 在每次使用前重新计算 monthly_rate 和其他相关变量
                monthly_rate = current_rate / 100 / 12

                # 根据还款类型重新计算当期的还款内容
                if repayment_type == "equal_principal":
                    interest = remaining_principal * monthly_rate
                    principal_payment = monthly_principal
                elif repayment_type == "equal_payment":
                    monthly_rate = initial_rate / 100 / 12
                    equal_monthly_payment = loan_amount * (monthly_rate * (1 + monthly_rate) ** total_months) / ((1 + monthly_rate) ** total_months - 1)
                    interest = remaining_principal * monthly_rate
                    principal_payment = equal_monthly_payment - interest
                else:
                    raise ValueError("不支持的还款类型")

                # 添加常规还款记录
                schedule.append({
                    '期数': month,
                    '还款日期': current_date.strftime('%Y-%m-%d'),
                    '类型': '正常还款',
                    '月供本金': principal_payment,
                    '月供利息': interest,
                    '剩余本金': remaining_principal - principal_payment,
                })

                # 更新剩余本金
                remaining_principal -= principal_payment

                # 标记该月份已经处理
                processed_months.add((current_date.year, current_date.month, current_date.day))
        if not prepayment_details:
            if (current_date.year, current_date.month, current_date.day) in processed_months:
                continue  # 如果该月份已经处理过，跳过重复处理

            # 在每次使用前重新计算 monthly_rate 和其他相关变量
            monthly_rate = current_rate / 100 / 12

            # 根据还款类型重新计算当期的还款内容
            if repayment_type == "equal_principal":
                interest = remaining_principal * monthly_rate
                principal_payment = monthly_principal
            elif repayment_type == "equal_payment":
                monthly_rate = initial_rate / 100 / 12
                equal_monthly_payment = loan_amount * (monthly_rate * (1 + monthly_rate) ** total_months) / ((1 + monthly_rate) ** total_months - 1)
                interest = remaining_principal * monthly_rate
                principal_payment = equal_monthly_payment - interest
            else:
                raise ValueError("不支持的还款类型")

            # 添加常规还款记录
            schedule.append({
                '期数': month,
                '还款日期': current_date.strftime('%Y-%m-%d'),
                '类型': '正常还款',
                '月供本金': principal_payment,
                '月供利息': interest,
                '剩余本金': remaining_principal - principal_payment,
            })

            # 更新剩余本金
            remaining_principal -= principal_payment

            # 标记该月份已经处理
            processed_months.add((current_date.year, current_date.month, current_date.day))

        # 如果剩余本金小于等于0.01，则视为全部还清
        if remaining_principal <= 0.01:
            remaining_principal = 0

        # 终止条件
        if remaining_principal <= 0:
            break

        # 递增月份
        current_date += relativedelta(months=+1)
        month += 1

    # 统一计算累计数据
    total_interest = 0.0
    total_principal = 0.0
    for row in schedule:
        total_principal += row['月供本金']
        total_interest += row['月供利息']
        row['累计已还本金'] = total_principal
        row['累计已还利息'] = total_interest

    # 检查并修正最后一期本金
    if schedule and abs(schedule[-1]['剩余本金']) > 1e-5:  # 如果最后一期仍有本金未还清
        last_row = schedule[-1]
        adjustment = last_row['剩余本金']
        last_row['月供本金'] -= adjustment  # 调整最后一期本金
        last_row['剩余本金'] = 0.0  # 强制设为 0
        last_row['累计已还本金'] = loan_amount  # 确保累计已还本金等于贷款总额
        last_row['月供总额'] = last_row['月供本金'] + last_row['月供利息']
    # 构建DataFrame
    df = pd.DataFrame(schedule)

    # 确保所有关键字段存在
    required_columns = ['月供本金', '月供利息', '月供总额', '剩余本金', '累计已还本金', '累计已还利息']
    for col in required_columns:
        if col not in df.columns:
            df[col] = 0.0

    # 安全计算累计字段（兜底机制）
    df['月供本金'] = df['月供本金'].fillna(0)
    df['月供利息'] = df['月供利息'].fillna(0)
    df['月供总额'] = df['月供本金'] + df['月供利息']

    # 使用高精度计算累计字段
    df['累计已还本金'] = df['月供本金'].cumsum().round(6)
    df['累计已还利息'] = df['月供利息'].cumsum().round(6)
    df['剩余本金'] = (loan_amount - df['累计已还本金']).round(6)

    # 最终保留两位小数输出
    df['月供本金'] = df['月供本金'].round(2)
    df['月供利息'] = df['月供利息'].round(2)
    df['剩余本金'] = df['剩余本金'].round(2)
    df['累计已还本金'] = df['累计已还本金'].round(2)
    df['累计已还利息'] = df['累计已还利息'].round(2)
    df['月供总额'] = df['月供总额'].round(2)

    # 按还款日期排序
    df['还款日期'] = pd.to_datetime(df['还款日期'])
    # df = df.sort_values('还款日期').reset_index(drop=True)

    return df


# -----------------------------
# Streamlit Web App 部分
# -----------------------------

# 国家公积金利率历史表
national_rate_table = [
    # date, <=5年首套, >5年首套, <=5年二套, >5年二套
    ('2015-03-01', 3.50, 4.00, None, None),
    ('2015-10-24', 2.75, 3.25, None, None),
    ('2022-10-01', 2.60, 3.10, 3.025, 3.575),
    ('2024-05-18', 2.35, 2.85, 2.775, 3.325),
    ('2025-05-07', 2.10, 2.60, 2.525, 3.075),
]


# 转换为 datetime 并处理不同利率类型
def build_rate_dict(rate_table, is_first_home, loan_years):
    rate_dict = {}
    for entry in rate_table:
        date_str, r_le5_first, r_gt5_first, r_le5_second, r_gt5_second = entry
        date = datetime.strptime(date_str, "%Y-%m-%d")
        if is_first_home:
            rate = r_le5_first if loan_years <= 5 else r_gt5_first
        else:
            rate = r_le5_second if loan_years <= 5 else r_gt5_second
        if rate is not None:
            rate_dict[date] = rate
    return rate_dict


def run_web_app():
    # 设置页面配置（包括图标）
    st.set_page_config(page_title="公积金贷款还款计划生成器", layout="wide",
                       page_icon="💰"  # 使用 emoji 图标，也可以使用本地图片路径
                       )

    # 设置标题（居中、字体稍小）
    st.markdown("""
    <style>
        .title {
            text-align: center;
            font-size: 1.5em;
            margin-top: 0.1em;  /* 减小顶部边距 */
            margin-bottom: 0.5em;
        }
    </style>
    <div class="title">公积金贷款还款计划生成器</div>
    """, unsafe_allow_html=True)

    # 用户输入界面
    st.sidebar.header("贷款参数设置")

    # 贷款金额和贷款年限放在同一行
    col1, col2 = st.sidebar.columns(2)
    with col1:
        loan_amount = st.number_input("贷款金额（元）", value=400000, step=1000)
    with col2:
        loan_years = st.number_input("贷款年限（年）", value=30, min_value=1, step=1)

    first_pay_date = st.sidebar.date_input("首次还款日期", value=datetime(2022, 9, 12))
    repayment_type = st.sidebar.selectbox("还款类型", ["等额本金", "等额本息"], index=0)
    is_first_home = st.sidebar.checkbox("是否首套房", value=True)

    st.sidebar.subheader("利率设置")
    initial_rate = st.sidebar.slider("基础年利率 (%)", min_value=2.0, max_value=6.0, value=3.25, step=0.05)
    use_national_rates = st.sidebar.checkbox("使用国家公积金利率", value=True)
    # simulate_rate_fluctuation = st.sidebar.checkbox("模拟利率浮动？")  # 暂时注释
    rate_adjustment_basis = st.sidebar.selectbox("利率调整基准日", ["每年1月1日", "每年放贷日"])

    # 默认设置 simulate_rate_fluctuation 为 False
    simulate_rate_fluctuation = False  # 添加此行以避免 NameError

    # 构建利率变更字典
    rate_changes = {}
    if use_national_rates:
        # 使用国家历史利率
        national_rate_changes = build_rate_dict(national_rate_table, is_first_home, loan_years)

        # 调整为只在利率调整基准日生效
        adjusted_rate_changes = {}
        for change_date in sorted(national_rate_changes.keys()):
            if rate_adjustment_basis == "每年1月1日":
                # 找出 change_date 之后的第一个1月1日
                candidate_year = change_date.year
                while True:
                    loan_day_this_year = datetime(candidate_year, 1, 1)
                    if loan_day_this_year > change_date:
                        next_effective_date = loan_day_this_year
                        break
                    candidate_year += 1
            else:  # 每年放贷日
                # 找出 change_date 之后的第一个放贷日
                candidate_year = first_pay_date.year
                while True:
                    try:
                        loan_day_this_year = datetime(candidate_year, first_pay_date.month, first_pay_date.day)
                    except ValueError:
                        loan_day_this_year = datetime(candidate_year, first_pay_date.month, 28)
                    if loan_day_this_year > change_date:
                        next_effective_date = loan_day_this_year
                        break
                    candidate_year += 1

            if next_effective_date > datetime.combine(first_pay_date, datetime.min.time()):
                adjusted_rate_changes[next_effective_date] = national_rate_changes[change_date]
                print(f"[DEBUG] 国家利率变更 {change_date} → 生效日: {next_effective_date}, 利率: {national_rate_changes[change_date]}")

        rate_changes = adjusted_rate_changes
    elif simulate_rate_fluctuation:
        fluctuation_range = st.sidebar.slider("利率浮动范围 (%)", -1.0, 1.0, (0.0, 0.2), step=0.05)
        num_rate_changes = st.sidebar.slider("利率变动次数", 0, 5, 3)
        import random

        # 根据选择的基准日生成利率变更日期
        if rate_adjustment_basis == "每年1月1日":
            fluctuation_dates = [datetime(year, 1, 1) for year in range(first_pay_date.year + 1, first_pay_date.year + num_rate_changes + 1)]
        else:  # "每年放贷日"
            fluctuation_dates = [datetime(first_pay_date.year + i, first_pay_date.month, first_pay_date.day) for i in range(1, num_rate_changes + 1)]

        fluctuation_dates = sorted(fluctuation_dates)
        rate_changes = {
            date: round(initial_rate + random.uniform(*fluctuation_range), 4)
            for date in fluctuation_dates
        }
    else:
        st.sidebar.write("手动输入利率变更（JSON格式）：格式为 {变更日期: 利率%}")
        st.sidebar.write("示例：", "{20230101:3.1,20250101:2.85,20260101:2.6}")
        rate_changes_input = st.sidebar.text_area("利率变更", "{}")
        try:
            rate_changes = {datetime.strptime(str(date), "%Y%m%d").date(): rate for date, rate in ast.literal_eval(rate_changes_input).items()}
        except Exception as e:
            st.error(f"利率变更输入格式错误: {e}")

    st.sidebar.subheader("提前还款设置")
    prepay_count = st.sidebar.number_input("提前还款次数", 0, 5, 1)
    prepayment_details = []
    for i in range(prepay_count):
        col1, col2 = st.sidebar.columns(2)
        with col1:
            pdate = st.date_input(f"第{i + 1}次还款日", datetime(2026, i % 12 + 1, 1), key=f"date_{i}")
        with col2:
            pamount = st.number_input(f"第{i + 1}次还款金额", value=50000, step=5000, key=f"amount_{i}")
        prepayment_details.append({'date': pdate, 'amount': pamount})

    if st.button("生成还款计划"):
        # 调整参数
        params = {
            'loan_amount': loan_amount,
            'loan_years': loan_years,
            'first_pay_date': datetime.combine(first_pay_date, datetime.min.time()),
            'initial_rate': initial_rate,
            'rate_changes': rate_changes,
            'prepayment_details': prepayment_details,
            'repayment_type': "equal_principal" if repayment_type == "等额本金" else "equal_payment"
        }

        # 生成计划
        df = generate_repayment_schedule(**params)

        # 展示数据
        st.subheader("还款计划详情")

        # 高亮提前还款行
        def highlight_prepayment(row):
            return ['background-color: #ffe6e6' if row['类型'] == '提前还款' else '' for _ in row]

        # 只展示关键字段
        display_columns = ['期数', '还款日期', '类型', '月供本金', '月供利息', '剩余本金', '累计已还本金', '累计已还利息', '月供总额']
        styled_df = df[display_columns].style.apply(highlight_prepayment, axis=1).format({
            "月供利息": "{:.2f}",
            "月供本金": "{:.2f}",
            "剩余本金": "{:.2f}",
            "累计已还本金": "{:.2f}",
            "累计已还利息": "{:.2f}",
            "月供总额": "{:.2f}"
        })

        # 使用 HTML 和 CSS 控制表格样式，防止水平滚动
        st.markdown("""
        <style>
            .dataframe td {
                white-space: normal !important;
                word-wrap: break-word !important;
                max-width: 200px !important;
            }
            .dataframe th {
                white-space: normal !important;
                word-wrap: break-word !important;
                max-width: 200px !important;
            }
        </style>
        """, unsafe_allow_html=True)

        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600)  # 默认展示15行左右


if __name__ == "__main__":
    # if '--web' in sys.argv:
    run_web_app()
    # else:
    #     # 原始命令行测试用例
    #     params = {
    #         'loan_amount': 400000,
    #         'loan_years': 30,
    #         'first_pay_date': datetime(2022, 9, 12),
    #         'initial_rate': 3.25,
    #         'rate_changes': {
    #             datetime(2023, 1, 1): 3.1,
    #             datetime(2025, 1, 1): 2.85,
    #             datetime(2026, 1, 1): 2.6
    #         },
    #         'prepayment_details': [{'date': datetime(2026, 1, 1), 'amount': 50000},{'date': datetime(2026, 2, 1), 'amount': 50000}],
    #         # 'repayment_type': "equal_principal"
    #         'repayment_type': "equal_payment"
    #     }

    #     repayment_df = generate_repayment_schedule(**params)
    #     print("[INFO] 第1期：", repayment_df.iloc[0].to_dict())
    #     print("[INFO] 第12期：", repayment_df.iloc[11].to_dict())
    #     print("[INFO] 第13期（2023-09-12）：", repayment_df.iloc[12].to_dict())
    #     print("[INFO] 第24期：", repayment_df.iloc[23].to_dict())
    #     print("[INFO] 第25期（2024-09-12）：", repayment_df.iloc[24].to_dict())
    #     print("[INFO] 第36期：", repayment_df.iloc[35].to_dict())
    #     print("[INFO] 第37期（2025-09-12）：", repayment_df.iloc[36].to_dict())
    #     print(repayment_df[['还款日期', '月供利息', '剩余本金', '累计已还本金']].head(40).to_string(index=False))