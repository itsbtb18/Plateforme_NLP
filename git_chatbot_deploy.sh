#!/bin/bash
# Git Deployment Script for Chatbot Upgrade v6.0
# Author: Antigravity

# 1. Create and switch to a new feature branch
echo "🚀 Creating feature branch..."
git checkout -b feature/chatbot-upgrade-v6

# 2. Stage all changes (edits, new files, and deletions)
echo "📦 Staging all changes..."
git add .

# 3. Commit changes
echo "💾 Committing changes..."
git commit -m "Upgrade chatbot: Advanced RAG Pipeline (Phases 1-8)"

# 4. Push the feature branch to remote
echo "📤 Pushing feature branch to origin..."
git push origin feature/chatbot-upgrade-v6

# 5. Switch back to dev branch
echo "🔄 Switching back to dev..."
git checkout dev

# 6. Merge the feature branch into dev
echo "🔀 Merging feature branch into dev..."
git merge feature/chatbot-upgrade-v6

# 7. Push updated dev to remote
echo "🚀 Pushing updated dev to origin..."
git push origin dev

echo "✅ Deployment complete! Your chatbot upgrade is now on 'dev' and 'feature/chatbot-upgrade-v6'."
