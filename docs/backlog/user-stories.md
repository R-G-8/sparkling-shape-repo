# Initial backlog (from the user journey)

Each story becomes a GitHub issue labeled `user story`. Acceptance criteria are
the spec handed to the coding agent.

## 1. Create an account
As a new user, I want to sign up with a username and password, so that my
watch history and rankings are saved to me.
- [ ] `/signup` creates an account and logs me in, landing on `/dashboard`
- [ ] Invalid or mismatched passwords show an error and create nothing
- [ ] `/dashboard` redirects to `/login` when logged out
- [ ] Works on phone and desktop widths

## 2. Find my watch-history download page
As a new user, I want my first screen to tell me how to download my watch
history from my streaming service, so that I can import it without searching.
- [ ] After first login, the dashboard shows a "Choose your service" step
- [ ] Choosing Netflix shows step-by-step instructions and a link to `netflix.com/viewingactivity`
- [ ] At least Netflix is supported; other services show "coming soon"

## 3. Upload my Netflix watch history
As a user, I want to upload my Netflix viewing-activity CSV, so that the app
knows what I've watched.
- [ ] An upload form accepts a `.csv` up to 5 MB
- [ ] Each row (Title, Date) is saved to the database for my account, not to disk
- [ ] Re-uploading the same file doesn't create duplicates
- [ ] A malformed file shows a clear error and saves nothing
- [ ] After upload I see how many titles were imported

## 4. Rank what I've watched
As a user, I want to compare titles I've watched two at a time and pick the
one I liked more (swipe or tap), so that the app builds my personal ranking.
- [ ] The ranking screen shows two titles from my history
- [ ] Picking one records the comparison and shows the next pair
- [ ] My ranked list page orders titles by my comparisons
- [ ] Works with touch (swipe) on phones and clicks on desktop

## 5. See details about a title
As a user, I want to see an overview, cast, and poster for a title, so that I
remember what it is when ranking.
- [ ] Title details come from an external movie data source and are cached in the database
- [ ] If the source is unavailable, the title still shows with its name only
- [ ] Tests mock the external source

## 6. Get AI recommendations
As a user, I want recommendations based on my rankings and the services I
have, so that I find something new to watch.
- [ ] The server calls the LLM through OpenRouter (never from the browser)
- [ ] I see at least 5 recommendations, each with a one-line reason
- [ ] Recommendations exclude titles already in my history
- [ ] If the LLM call fails, I see a friendly error, not a crash
- [ ] Tests mock the LLM

## 7. Follow friends
As a user, I want to find and follow friends, so that I can see what they like.
- [ ] I can search users by username and follow or unfollow them
- [ ] A friend's profile shows their top-ranked titles

## 8. Trending among friends
As a user, I want a trending page of the most popular titles among my friends
and across the app, so that I see what people are watching.
- [ ] "Friends" tab ranks titles by how many friends ranked them highly
- [ ] "Everyone" tab does the same across all users
- [ ] Pages load in under a second with 1,000 users of seed data

## 9. Watch-personality profile
As a user, I want an AI-written "watch personality" from my history, so that I
get a fun summary I can share with friends.
- [ ] Generated on the server through OpenRouter from my top titles
- [ ] Stored so it isn't regenerated on every page view
- [ ] Tests mock the LLM
