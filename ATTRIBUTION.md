# Attribution and terms of the open feeds

Rows from these feeds carry the feed name in the `a` field, and their URL is the feed's own job URL, as each
feed's terms require. Anything shown to a person from these rows must credit the feed and link to that URL.

| Feed | Terms we found | What we do |
|---|---|---|
| Remotive (`remotive.com/api/remote-jobs`) | Credit Remotive and link back to the Remotive URL. Do not pass its jobs on to Google Jobs, LinkedIn, Jooble and similar. Jobs are delayed 24 hours. | Its `robots.txt` disallows `/api/*`, so the client refuses to call it. Blocked until Remotive agrees in writing. |
| Arbeitnow (`arbeitnow.com/api/job-board-api`) | Free to use, credit and link to Arbeitnow. | Read, credited as `arbeitnow`. |
| RemoteOK (`remoteok.com/api`) | Link back to the Remote OK URL with a followed link, and name Remote OK as the source. Logo not used. | Read, credited as `remoteok`; URL is the RemoteOK URL. |
| Himalayas (`himalayas.app/jobs/api`) | Credit and link to Himalayas. | Read with cursor paging, 1 request a second, credited as `himalayas`. |
| Jobicy (`jobicy.com/api/v2/remote-jobs`) | Credit Jobicy with a direct link; apply buttons must go to the job URL in the feed. | Read, credited as `jobicy`. |
| The Muse (`themuse.com/api/public/jobs`) | Public API, no key for low volume. Credit The Muse. | Read, capped at 100 pages a run, credited as `themuse`. |
| We Work Remotely (RSS) | Credit and link back. | Read ten category feeds, credited as `weworkremotely`. |

If a feed changes its terms, remove it from `jobalfred_index/adapters/feeds.py`.
