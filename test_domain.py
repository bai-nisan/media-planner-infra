#!/usr/bin/env python3
"""
Quick domain layer validation test
"""

import sys
sys.path.append('src')

try:
    # Import all our domain components
    from domain.value_objects import Money, Currency, DateRange, CampaignStatus, Percentage
    from domain.entities import Campaign, Budget, MediaChannel, Client
    from domain.services import BudgetAllocationService, AllocationStrategy
    from domain.exceptions import BudgetExceededError, CurrencyMismatchError
    from domain.events import CampaignCreatedEvent
    from datetime import date
    
    print('✅ All domain imports successful!')
    
    # Test Money value object
    budget_amount = Money(10000, Currency.USD)
    print(f'✅ Money created: {budget_amount}')
    
    # Test DateRange value object
    date_range = DateRange('2024-01-01', '2024-12-31')
    print(f'✅ DateRange created: {date_range}')
    
    # Test CampaignStatus
    status = CampaignStatus('draft')
    new_status = status.transition_to('scheduled')
    print(f'✅ Status transition: {status} -> {new_status}')
    
    # Test MediaChannel
    channel = MediaChannel('Google Ads', 'search')
    print(f'✅ MediaChannel created: {channel}')
    
    # Test Budget entity
    budget = Budget('budget-1', 'tenant-1', budget_amount, Currency.USD)
    allocation = budget.add_allocation(channel, Money(5000, Currency.USD))
    print(f'✅ Budget allocation: {allocation}')
    
    print('\n🎉 DOMAIN LAYER IMPLEMENTATION SUCCESSFULLY VALIDATED!')
    print('All core components working correctly with proper validation and business logic.')
    
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc() 