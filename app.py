import json

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title='AI Job Exposure Explorer', page_icon='🧭', layout='wide')

LABELS = ['exposed', 'augmented', 'resistant']
COLORS = {'exposed': '#d1495b', 'augmented': '#edae49', 'resistant': '#00798c'}
RATING_TEXT = {'can_do': 'AI can do it', 'can_help': 'AI can help', 'needs_person': 'Needs a person'}
MIN_POSTINGS = 20   # below this, a role's label mix is too noisy to trust


@st.cache_data
def load():
    d = 'app_data'
    info = json.load(open(f'{d}/build_info.json'))
    posts = pd.read_csv(f'{d}/labeled_postings.csv')
    posts['company_name'] = posts['company_name'].fillna('company not listed')
    sectors = pd.read_csv(f'{d}/sector_summary.csv')
    ai_share = pd.read_csv(f'{d}/ai_share_us.csv', parse_dates=['date'])
    return info, posts, sectors, ai_share


info, posts, sectors, ai_share = load()


def api_key():
    try:
        return st.secrets['GROQ_API_KEY']
    except Exception:          # no secrets file, or the key is not in it
        return None


def label_from_tasks(tasks):
    """Same rule as the notebook: task ratings -> label and exposure score."""
    ratings = [t.get('ai') for t in tasks if t.get('ai') in RATING_TEXT]
    if not ratings:
        return None, None
    n = len(ratings)
    do, help_, person = (ratings.count(r) / n for r in ('can_do', 'can_help', 'needs_person'))
    label = 'resistant' if person >= 0.5 else 'exposed' if do >= 0.5 else 'augmented'
    return label, do + 0.5 * help_


def tasks_table(tasks):
    return pd.DataFrame([{'Task': t.get('task', ''), 'AI rating': RATING_TEXT.get(t.get('ai'), '?')} for t in tasks])


def label_mix(g):
    mix = g['label'].value_counts(normalize=True).reindex(LABELS, fill_value=0)
    return pd.DataFrame({'label': mix.index, 'share': (mix.values * 100).round(1)})


# ---------------- header ----------------
st.title('🧭 AI Job Exposure Explorer')
st.caption(f"**Last built on {info['built_on']}** · postings listed {info['postings_listed_from']} to "
           f"{info['postings_listed_to']} · {info['postings_labeled']:,} postings labeled · LLM: {info['llm']} "
           f"(prompt {info['prompt_version']})" + (' · **trial version**' if info.get('trial') else ''))

if info.get('note'):
    st.info(info['note'])

tab0, tab1, tab2, tab3 = st.tabs(['Overview', 'Explore a role', 'Check a job posting', 'How it works'])

# ---------------- tab 0: overview ----------------
with tab0:
    a, b, c = st.columns(3)
    mix = posts['label'].value_counts(normalize=True)
    a.metric('Exposed', f"{mix.get('exposed', 0):.0%}", help='Half or more of the tasks AI can already do')
    b.metric('Augmented', f"{mix.get('augmented', 0):.0%}", help='AI mostly helps, or a mix')
    c.metric('Resistant', f"{mix.get('resistant', 0):.0%}", help='Half or more of the tasks need a person')

    st.subheader('Exposure vs. hiring since our data was collected')
    st.caption(f"Each dot is a sector. Right = more exposed to AI in our postings. Down = hiring fell more than the "
               f"market from {info['trend_measured_from']} to {info['indeed_data_through']} (Indeed). Sectors that are "
               "both exposed and hiring less are where postings may understate the effect of AI.")
    plot = sectors.dropna(subset=['vs_market_pts']).rename(columns={
        'avg_exposure_score': 'Exposure score', 'vs_market_pts': 'Hiring vs. market (pts)', 'postings': 'Postings'})
    st.scatter_chart(plot, x='Exposure score', y='Hiring vs. market (pts)', size='Postings', height=420)
    st.dataframe(plot[['sector', 'Postings', 'Exposure score', 'Hiring vs. market (pts)']]
                 .sort_values('Exposure score', ascending=False).round(2), hide_index=True, use_container_width=True)

# ---------------- tab 1: explore ----------------
with tab1:
    counts = posts['sector'].value_counts()
    c1, c2 = st.columns(2)
    sector = c1.selectbox('Sector', counts.index, format_func=lambda s: f'{s} ({counts[s]} postings)')
    in_sector = posts[posts['sector'] == sector]
    roles = in_sector['role'].value_counts()
    role = c2.selectbox('Role', ['All roles in this sector'] + list(roles.index),
                        format_func=lambda r: r if r.startswith('All') else f'{r} ({roles[r]})')
    g = in_sector if role.startswith('All') else in_sector[in_sector['role'] == role]

    m1, m2, m3 = st.columns(3)
    m1.metric('Postings', len(g))
    m2.metric('Average exposure score', f"{g['exposure_score'].mean():.2f}", help='0 = no tasks AI can do or help with, 1 = AI can do every task')
    m3.metric('AI in the job duties', f"{g['ai_mention'].isin(['build_ai', 'use_ai_tools']).mean():.0%}",
              help='Share of postings where the job builds AI or must use AI tools. Company-only mentions are not counted.')

    if len(g) < MIN_POSTINGS:
        st.warning(f'Only {len(g)} postings: too few to trust this mix. Treat it as examples, not a result.')

    left, right = st.columns([3, 2])
    with left:
        st.subheader('Label mix')
        st.altair_chart(alt.Chart(label_mix(g)).mark_bar().encode(
            x=alt.X('share:Q', title='% of postings', scale=alt.Scale(domain=[0, 100])),
            y=alt.Y('label:N', sort=LABELS, title=None),
            color=alt.Color('label:N', scale=alt.Scale(domain=LABELS, range=[COLORS[l] for l in LABELS]), legend=None),
            tooltip=['label', 'share']).properties(height=160), use_container_width=True)
        st.caption('Each posting gets its own label, so a role can be a mix. A wide mix means the same title covers '
                   'very different jobs.')
    with right:
        st.subheader('Top skills asked for')
        skills = pd.Series([s.strip().lower() for x in g['skills'].dropna() for s in x.split(';') if s.strip()])
        st.write(', '.join(skills.value_counts().head(10).index) or 'No skills extracted.')

        row = sectors[sectors['sector'] == sector]
        if not row.empty and pd.notna(row['postings_change_pct'].iloc[0]):
            chg, vs = row['postings_change_pct'].iloc[0], row['vs_market_pts'].iloc[0]
            st.subheader('Is this sector still hiring?')
            st.metric(f"Postings change since {info['trend_measured_from']} (Indeed)", f'{chg:+.0f}%',
                      f'{vs:+.0f} pts vs. all jobs', delta_color='normal')
            if vs < -10:
                st.info('This sector is hiring much less than the market. If AI is part of the reason, the most '
                        'affected jobs may be missing from the postings, so exposure here could be **understated**.')

    st.subheader('Example postings')
    for lab in LABELS:
        ex = g[g['label'] == lab].head(2)
        for _, p in ex.iterrows():
            with st.expander(f"{lab.upper()} · {p['title']} at {p['company_name']} (score {p['exposure_score']:.2f})"):
                st.dataframe(tasks_table(json.loads(p['tasks'])), hide_index=True, use_container_width=True)
                st.caption(str(p['description']) + '…')

# ---------------- tab 2: paste a posting ----------------
with tab2:
    st.write('Paste a job posting. The model lists its main tasks and rates each one; the label comes from those '
             'ratings with the same rule used for the dataset.')
    title = st.text_input('Job title')
    text = st.text_area('Job description', height=250)
    if st.button('Analyze', type='primary'):
        if len(text) < 200:
            st.error('Please paste the full description (at least a few sentences), then try again.')
        elif not api_key():
            st.error('The app has no API key set up, so it cannot analyze new postings. Add GROQ_API_KEY in the app secrets.')
        else:
            from groq import Groq
            prompt = info['prompt'].format(sectors=', '.join(info['sectors']), title=title or 'Not given', description=text[:4000])
            try:
                with st.spinner('Reading the posting...'):
                    reply = Groq(api_key=api_key()).chat.completions.create(
                        model=info.get('groq_model', info['llm']), temperature=0, response_format={'type': 'json_object'},
                        messages=[{'role': 'user', 'content': prompt}])
                answer = json.loads(reply.choices[0].message.content)
            except Exception as e:
                st.error(f'The model could not answer ({type(e).__name__}). Wait a minute and try again.')
                st.stop()
            label, score = label_from_tasks(answer.get('tasks', []))
            if label is None:
                st.error('The model did not return any rated tasks, so there is no label. Try a longer description.')
            else:
                st.markdown(f"### <span style='color:{COLORS[label]}'>{label.title()}</span> · exposure score {score:.2f}",
                            unsafe_allow_html=True)
                st.dataframe(tasks_table(answer['tasks']), hide_index=True, use_container_width=True)
                st.write('**Skills:** ' + ', '.join(answer.get('skills', [])))
                st.write('**Sector:** ' + str(answer.get('sector', 'unknown')))
                st.caption('This is one posting, labeled from its tasks. Wording written with AI tools should not change '
                           'the result much, but check the task list: if it is wrong, the label is wrong.')

# ---------------- tab 3: how it works ----------------
with tab3:
    st.subheader('What the labels mean')
    st.write('The model lists 3–6 main tasks from the posting and rates each one. A fixed rule turns the ratings into a label:')
    st.table(pd.DataFrame({
        'Label': ['Resistant', 'Exposed', 'Augmented'],
        'Rule (checked in this order)': ['Half or more of the tasks need a person (physical, hands-on, in-person)',
                                         'Half or more of the tasks AI can already do',
                                         'Everything else: AI mostly helps, or a mix'],
    }))
    st.write('A job can be exposed to AI *and* benefit from it: that is what "augmented" captures. '
             'The exposure score (0 to 1) keeps the detail the label leaves out.')

    st.subheader('AI keeps changing')
    st.write(f"Our postings are from {info['postings_listed_from'][:7]} to {info['postings_listed_to'][:7]}. "
             'Since then, the share of US job postings that mention AI has kept rising (Indeed Hiring Lab):')
    st.line_chart(ai_share.set_index('date')['AI_share_postings'].resample('MS').mean(), y_label='% of US postings')

    st.subheader('Limits to keep in mind')
    st.markdown(f"""
- **Selection:** postings only show jobs employers are still hiring for. If AI already cut some roles, they are missing here, so the most affected jobs can look *less* exposed. We show Indeed's hiring trend by sector (from {info['trend_measured_from']} to {info['indeed_data_through']}) as a warning sign, not a correction.
- **AI-written postings:** many postings are now written with AI tools. We label the tasks, not the wording, and we separate AI in the job duties from AI in company boilerplate.
- **Snapshot:** a role that looks resistant in this data may not be today. Check the build date above.
- **Trial version:** {info['postings_labeled']:,} postings, so most roles have few examples.
""")
    st.caption('Data: Kaggle "LinkedIn Job Postings (2023–2024)" by arshkon; Indeed Hiring Lab AI Tracker and Job Postings Index (CC BY 4.0).')
