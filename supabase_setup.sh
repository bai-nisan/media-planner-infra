#!/bin/bash

# Supabase CLI Setup Script for Media Planner Project
# Run this script to connect to your existing Supabase project

echo "🚀 Setting up Supabase CLI for Media Planner Project"

# Check if Supabase CLI is installed
if ! command -v supabase &> /dev/null; then
    echo "❌ Supabase CLI not found. Installing via Homebrew..."
    brew install supabase/tap/supabase
else
    echo "✅ Supabase CLI found"
fi

# Check if already logged in
if supabase projects list &> /dev/null; then
    echo "✅ Already logged in to Supabase"
else
    echo "🔐 Please login to Supabase..."
    supabase login
fi

# Create supabase directory if it doesn't exist
if [ ! -d "supabase" ]; then
    echo "📁 Initializing Supabase configuration..."
    supabase init
fi

# Prompt for project reference
echo ""
echo "🔗 To link to your existing project, you need your project reference."
echo "Find it in your Supabase dashboard: Settings > General > Reference ID"
echo ""
read -p "Enter your project reference ID: " PROJECT_REF

if [ ! -z "$PROJECT_REF" ]; then
    echo "🔗 Linking to project: $PROJECT_REF"
    supabase link --project-ref "$PROJECT_REF"
    
    if [ $? -eq 0 ]; then
        echo "✅ Successfully linked to project!"
        
        # Test connection
        echo "🧪 Testing connection..."
        supabase status
        
        echo ""
        echo "🎉 Setup complete! You can now use:"
        echo "  supabase db connect     # Connect to database"
        echo "  supabase status         # Check project status"
        echo "  supabase secrets list   # List Edge Function secrets"
        echo "  supabase inspect db     # View database schema"
        
    else
        echo "❌ Failed to link to project. Please check your project reference."
    fi
else
    echo "❌ No project reference provided. Please run the script again."
fi 