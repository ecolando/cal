import re
from datetime import date
from src.common import utils
from src.modules.interfaces import Module


class Gradescope(Module):
    ROOT = 'https://www.gradescope.com'
    SEASONS = {'winter': 0, 'spring': 1, 'summer': 2, 'fall': 3, 'autumn': 3}

    def _init(self):
        # Extract authentication token from login page
        login_page_res = self.session.get(Gradescope.ROOT + '/login')
        login_page = Module.parse_html(login_page_res.text)
        token = None
        for form in login_page.find_all('form'):
            if form.get('action') == '/login':
                token_input = form.find('input', {'name': 'authenticity_token'})
                if token_input is not None:
                    token = token_input.get('value')
        if token is None:
            meta = login_page.find('meta', {'name': 'csrf-token'})
            if meta is not None:
                token = meta.get('content')

        if token is None:
            return print('Gradescope: could not find login authenticity token')

        # Login by submitting the same form data the browser sends
        login_payload = {
            'utf8': '✓',
            'authenticity_token': token,
            'session[email]': self.user,
            'session[password]': self.password,
            'session[remember_me]': 0,
            'commit': 'Log In',
            'session[remember_me_sso]': 0
        }
        login_response = self.session.post(
            Gradescope.ROOT + '/login',
            data=login_payload
        )

        # A successful login redirects away from the login page
        if login_response.ok and not login_response.url.rstrip('/').endswith('/login'):
            self.initialized = True
        else:
            print('Gradescope: login failed, check GRADESCOPE_USER / GRADESCOPE_PASSWORD')

    def _main(self, assignments: dict):
        dashboard_res = self.session.get(Gradescope.ROOT + '/account')
        dashboard = Module.parse_html(dashboard_res.text)

        for course_entry in Gradescope._get_current_courses(dashboard):
            shortname = course_entry.find(class_='courseBox--shortname')
            if shortname is None:
                continue
            course_name = shortname.get_text(strip=True)
            course_link = course_entry.get('href')

            # Retrieve assignment information
            course_dashboard_res = self.session.get(Gradescope.ROOT + course_link)
            course_dashboard = Module.parse_html(course_dashboard_res.text)
            assignment_table = course_dashboard.find('tbody')
            if assignment_table is None:
                continue

            course_assignments = assignments.setdefault(course_name, [])
            for row in assignment_table.find_all('tr'):
                due_date = Gradescope._get_assignment_due_date(row)
                if due_date is not None:         # Only add assignment if it has a due date
                    title = Gradescope._get_assignment_title(row)
                    status = Gradescope._get_assignment_status(row)
                    link = Gradescope._get_assignment_link(row, course_link)
                    submitted = (status is not None and status != 'No Submission')

                    # Add to assignments list
                    course_assignments.append(utils.get_assignment_dict(
                        title,
                        course_name,
                        due_date,
                        link,
                        submitted
                    ))

    @staticmethod
    def _get_current_courses(dashboard):
        """Returns the course links for the current term's student courses."""

        course_lists = dashboard.find_all('div', {'class': 'courseList'})
        if len(course_lists) == 0:
            return []

        # Prefer the list under the "Student Courses" heading, otherwise the last list
        # (instructor courses are listed first)
        student_courses = course_lists[-1]
        for course_list in course_lists:
            heading = course_list.find_previous(['h1', 'h2'])
            if heading is not None and 'student' in heading.get_text().lower():
                student_courses = course_list
                break

        # Group courses by term ("Fall 2026", "Spring 2026", ...)
        terms = []
        for term_courses in student_courses.find_all('div', {'class': 'courseList--coursesForTerm'}):
            term_label = term_courses.find_previous_sibling('div', {'class': 'courseList--term'})
            label = term_label.get_text(strip=True) if term_label is not None else ''
            terms.append((Gradescope._term_key(label), label, term_courses))
        if len(terms) == 0:
            return []

        # Pick the most recent term that has already started, so prior-year and
        # upcoming-but-not-started terms are skipped
        today = date.today()
        now_key = (today.year, Gradescope._season_for_month(today.month))
        dated = [t for t in terms if t[0] is not None and t[0] <= now_key]
        if len(dated) > 0:
            current_key = max(t[0] for t in dated)
            selected = [t for t in dated if t[0] == current_key]
        else:
            selected = [terms[0]]    # Gradescope lists the newest term first

        print('Gradescope: using term(s) ' + ', '.join(t[1] or '(unnamed)' for t in selected))
        courses = []
        for _, _, term_courses in selected:
            courses.extend(term_courses.find_all('a', {'class': 'courseBox'}))
        return courses

    @staticmethod
    def _term_key(label):
        """Converts a term label like 'Fall 2026' into a sortable (year, season) tuple."""

        match = re.search(r'(winter|spring|summer|fall|autumn)\D*(\d{4})', label, re.IGNORECASE)
        if match is None:
            return None
        return int(match.group(2)), Gradescope.SEASONS[match.group(1).lower()]

    @staticmethod
    def _season_for_month(month):
        if month <= 5:
            return Gradescope.SEASONS['spring']
        if month <= 7:
            return Gradescope.SEASONS['summer']
        return Gradescope.SEASONS['fall']

    @staticmethod
    def _get_assignment_title(row):
        """Returns the title of an assignment given its row in the table."""

        heading = row.find('th')
        if heading is None:
            return ''
        title = heading.find('a')
        if title is None:
            title = heading.find('button')
        if title is None:
            title = heading
        return title.get_text(strip=True)

    @staticmethod
    def _get_assignment_due_date(row):
        """Returns the due date of an assignment given its row in the table."""

        due_date = row.find('time', {'class': 'submissionTimeChart--dueDate'})
        if due_date is None:
            return None
        # The datetime attribute includes the year and timezone; the visible text does not
        return due_date.get('datetime') or due_date.get_text(strip=True)

    @staticmethod
    def _get_assignment_status(row):
        """Returns the submission status of an assignment given its row in the table."""

        status = row.find('div', {'class': 'submissionStatus--text'})
        if status is None:
            status = row.find('div', {'class': 'submissionStatus--score'})
        if status is None:
            return None
        return status.get_text(strip=True)

    @staticmethod
    def _get_assignment_link(row, course_link):
        """Returns a link to the assignment."""

        link = course_link
        primary_link = row.find('th', {'class': 'table--primaryLink'})
        if primary_link is not None:
            anchor = primary_link.find('a')
            if anchor is not None and anchor.get('href'):
                link = anchor.get('href')
        return Gradescope.ROOT + link
