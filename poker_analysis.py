import pandas as pd
import re
from collections import defaultdict
from typing import Dict, List, Tuple

class PokerVPIPAnalyzer:
    def __init__(self, csv_file_path: str):
        """Initialize the analyzer with the poker log CSV file."""
        self.csv_file_path = csv_file_path
        self.df = None
        self.hands = []
        self.player_stats = defaultdict(lambda: {
            'hands_dealt': 0,
            'vpip_hands': 0,
            'total_put_in_pot': 0.0,
            'total_winnings': 0.0,
            'wins': 0,
            'buy_ins': 0.0,
            'final_stack': 0.0,
            'cash_outs': 0.0,
            'admin_adjustments': 0.0,
            'hand_types_won': defaultdict(int),
            'betting_phase_amounts': {
                'preflop': 0.0,
                'flop': 0.0,
                'turn': 0.0,
                'river': 0.0
            }
        })
        
    def load_data(self):
        """Load the CSV file."""
        self.df = pd.read_csv(self.csv_file_path)
        print(f"Loaded {len(self.df)} entries from {self.csv_file_path}")
        
    def extract_player_name(self, entry: str) -> str:
        """Extract player name from an entry string."""
        match = re.match(r'^"([^"]+)"', entry)
        return match.group(1) if match else None
        
    def extract_amount(self, entry: str) -> float:
        """Extract monetary amount from an entry string."""
        # Look for patterns like "calls 4.00", "bets 28.50", "raises to 11.00"
        amount_match = re.search(r'(\d+\.\d+)', entry)
        return float(amount_match.group(1)) if amount_match else 0.0
        
    def is_vpip_action(self, entry: str) -> bool:
        """
        Determine if an action counts as VPIP (Voluntarily Put In Pot).
        VPIP includes: calls, bets, raises (but NOT forced blinds or ante)
        """
        # Exclude forced actions first
        forced_patterns = [
            r'posts a big blind',
            r'posts a small blind',
            r'\(big blind\)',
            r'\(small blind\)',
            r'\(ante\)'
        ]
        
        # Check if it's a forced action first
        for pattern in forced_patterns:
            if re.search(pattern, entry, re.IGNORECASE):
                return False
        
        # VPIP actions (voluntary money put in pot)
        vpip_patterns = [
            r'calls \d+\.\d+',                   # calls (not blind calls due to exclusion above)
            r'bets \d+\.\d+',                    # bets
            r'raises to \d+\.\d+',               # raises
            r'posts a bet of \d+\.\d+'           # voluntary posts (like bomb pot bets)
        ]
                
        # Check if it's a VPIP action
        for pattern in vpip_patterns:
            if re.search(pattern, entry, re.IGNORECASE):
                return True
                
        return False
        
    def extract_hand_type(self, entry: str) -> str:
        """Extract the hand type from a winning entry."""
        # Look for patterns like "collected X from pot with [hand type]"
        patterns = [
            r'with (Straight Flush)',
            r'with (Four of a Kind|four of a kind [^(]+)',
            r'with (Full House|full house [^(]+)',
            r'with (Flush|flush [^(]+)',
            r'with (Straight[^,]*)',
            r'with (Three of a Kind|three of a kind [^(]+)',
            r'with (Two Pair[^,]*|two pair [^(]+)',
            r'with (One Pair|Pair[^,]*|pair [^(]+)',
            r'with ([A-Z] High)',
            r'with (hi hand|low hand)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, entry, re.IGNORECASE)
            if match:
                hand_type = match.group(1).lower()
                # Normalize hand types
                if 'straight flush' in hand_type:
                    return 'Straight Flush'
                elif 'four of a kind' in hand_type or 'four of a kind' in hand_type:
                    return 'Four of a Kind'
                elif 'full house' in hand_type:
                    return 'Full House'
                elif 'flush' in hand_type and 'straight' not in hand_type:
                    return 'Flush'
                elif 'straight' in hand_type:
                    return 'Straight'
                elif 'three of a kind' in hand_type:
                    return 'Three of a Kind'
                elif 'two pair' in hand_type:
                    return 'Two Pair'
                elif 'pair' in hand_type or 'one pair' in hand_type:
                    return 'One Pair'
                elif 'high' in hand_type:
                    return 'High Card'
                else:
                    return 'Other'
        
        return 'Didn\'t Show'
        
    def parse_buy_ins_and_stacks(self):
        """Parse buy-ins, cash-outs, admin adjustments and final stacks from the log."""
        # Sort data by order (chronological order) since the CSV is in reverse
        sorted_df = self.df.sort_values('order')
        
        for _, row in sorted_df.iterrows():
            entry = str(row['entry'])
            
            # Look for buy-ins/approvals
            buy_in_match = re.search(r'approved the player "([^"]+)" participation with a stack of (\d+(?:\.\d+)?)', entry)
            if buy_in_match:
                player = buy_in_match.group(1)
                amount = float(buy_in_match.group(2))
                self.player_stats[player]['buy_ins'] += amount
                continue
                
            # Look for admin stack updates (from X to Y)
            stack_update_match = re.search(r'updated the player "([^"]+)" stack from (\d+(?:\.\d+)?) to (\d+(?:\.\d+)?)', entry)
            if stack_update_match:
                player = stack_update_match.group(1)
                from_amount = float(stack_update_match.group(2))
                to_amount = float(stack_update_match.group(3))
                # Only count as admin adjustment if stack increased (positive adjustment)
                if to_amount > from_amount:
                    adjustment = to_amount - from_amount
                    self.player_stats[player]['admin_adjustments'] += adjustment
                continue
                
            # Look for admin stack resets
            stack_reset_match = re.search(r'reseting to (\d+(?:\.\d+)?) chips', entry)
            if stack_reset_match:
                # Find the player name from previous lines or context
                # This is more complex, but for now we'll skip this pattern
                # as it's usually followed by an "updated" entry anyway
                continue
                
            # Look for cash-outs (player quits with money)
            cash_out_match = re.search(r'"([^"]+)" quits the game with a stack of (\d+(?:\.\d+)?)', entry)
            if cash_out_match:
                player = cash_out_match.group(1)
                amount = float(cash_out_match.group(2))
                self.player_stats[player]['cash_outs'] += amount
                continue
                
            # Look for final stacks (most recent "Player stacks:" entry will have final values)
            if 'Player stacks:' in entry:
                # Extract all players and their stacks
                # Format: #1 "Greg @ bTWHIJcaFV" (996.37) | #2 "Tobi @ C5IYwkBaOk" (127.50)
                stack_matches = re.findall(r'"([^"]+)"\s*\((\d+(?:\.\d+)?)\)', entry)
                for player, stack in stack_matches:
                    self.player_stats[player]['final_stack'] = float(stack)
                    
        print("Buy-ins, cash-outs, admin adjustments and final stacks parsed")
        
    def parse_hands(self):
        """Parse the log entries to identify individual hands and actions."""
        # Sort data by order (chronological order) since the CSV is in reverse
        sorted_df = self.df.sort_values('order')
        
        current_hand = None
        current_hand_players = set()
        current_phase = 'preflop'  # Track betting phase
        
        for _, row in sorted_df.iterrows():
            entry = str(row['entry'])
            
            # Check for hand start
            hand_start_match = re.search(r'starting hand #(\d+)', entry)
            if hand_start_match:
                # Start new hand
                hand_number = int(hand_start_match.group(1))
                current_hand = {
                    'hand_number': hand_number,
                    'actions': [],
                    'players_dealt': [],
                    'winners': [],
                    'phases': {'preflop': [], 'flop': [], 'turn': [], 'river': []}
                }
                current_hand_players = set()
                current_phase = 'preflop'
                continue
                
            # Check for betting phases
            if current_hand:
                if 'Flop:' in entry:
                    current_phase = 'flop'
                    continue
                elif 'Turn:' in entry:
                    current_phase = 'turn'
                    continue
                elif 'River:' in entry:
                    current_phase = 'river'
                    continue
                
            # Check for player stacks (indicates who was dealt into the hand)
            if current_hand and 'Player stacks:' in entry:
                # Extract all players from the stack info
                player_matches = re.findall(r'"([^"]+)"', entry)
                current_hand_players.update(player_matches)
                continue
                
            # Parse player actions
            player_name = self.extract_player_name(entry)
            if player_name and current_hand:
                action_info = {
                    'player': player_name,
                    'action': entry,
                    'amount': self.extract_amount(entry),
                    'is_vpip': self.is_vpip_action(entry) and current_phase == 'preflop',  # VPIP only for preflop
                    'phase': current_phase
                }
                current_hand['actions'].append(action_info)
                current_hand['phases'][current_phase].append(action_info)
                
                # Check for wins
                if 'collected' in entry and 'from pot' in entry:
                    amount = self.extract_amount(entry)
                    hand_type = self.extract_hand_type(entry)
                    current_hand['winners'].append({
                        'player': player_name,
                        'amount': amount,
                        'hand_type': hand_type
                    })
                    
            # Check for hand end
            if 'ending hand' in entry:
                if current_hand:
                    current_hand['players_dealt'] = list(current_hand_players)
                    self.hands.append(current_hand)
                current_hand = None
                current_hand_players = set()
                current_phase = 'preflop'
                continue
        
        # Don't forget the last hand
        if current_hand:
            current_hand['players_dealt'] = list(current_hand_players)
            self.hands.append(current_hand)
            
        print(f"Parsed {len(self.hands)} hands")
        
    def calculate_stats(self):
        """Calculate VPIP and other statistics for each player."""
        for hand in self.hands:
            # Track players dealt into this hand
            for player in hand['players_dealt']:
                self.player_stats[player]['hands_dealt'] += 1
                
            # Track VPIP actions and amounts put in pot by phase
            vpip_players_this_hand = set()
            for action in hand['actions']:
                player = action['player']
                amount = action['amount']
                phase = action['phase']
                
                # Track total money put in pot by phase (all actions with amounts except collections)
                if amount > 0 and 'collected' not in action['action']:
                    self.player_stats[player]['total_put_in_pot'] += amount
                    self.player_stats[player]['betting_phase_amounts'][phase] += amount
                    
                # Track VPIP (only preflop voluntary actions)
                if action['is_vpip']:
                    vpip_players_this_hand.add(player)
                    
            # Mark VPIP for players who voluntarily put money in preflop
            for player in vpip_players_this_hand:
                self.player_stats[player]['vpip_hands'] += 1
                
            # Track winnings and hand types
            for winner in hand['winners']:
                player = winner['player']
                amount = winner['amount']
                hand_type = winner['hand_type']
                self.player_stats[player]['total_winnings'] += amount
                self.player_stats[player]['wins'] += 1
                self.player_stats[player]['hand_types_won'][hand_type] += 1
                
        # Debug output
        print(f"\nPlayer stats summary:")
        for player, stats in list(self.player_stats.items())[:3]:
            print(f"{player}: {stats['hands_dealt']} hands, {stats['vpip_hands']} VPIP hands, "
                  f"${stats['total_put_in_pot']:.2f} put in, ${stats['total_winnings']:.2f} won")
                  
    def get_top_hand_types(self, player_stats: dict, n: int = 2) -> List[Tuple[str, int]]:
        """Get the top N hand types a player won with."""
        hand_types = player_stats['hand_types_won']
        if not hand_types:
            return [('No wins', 0)] * n
        
        sorted_types = sorted(hand_types.items(), key=lambda x: x[1], reverse=True)
        result = sorted_types[:n]
        
        # Pad with empty entries if needed
        while len(result) < n:
            result.append(('No wins', 0))
            
        return result
        
    def get_top_betting_phases(self, player_stats: dict, n: int = 2) -> List[Tuple[str, float]]:
        """Get the top N betting phases where a player bet the most."""
        phases = player_stats['betting_phase_amounts']
        sorted_phases = sorted(phases.items(), key=lambda x: x[1], reverse=True)
        result = sorted_phases[:n]
        
        # Pad with empty entries if needed
        while len(result) < n:
            result.append(('None', 0.0))
            
        return result
                  
    def generate_report(self) -> Dict:
        """Generate a comprehensive report of all player statistics."""
        report = {}
        
        for player, stats in self.player_stats.items():
            hands_dealt = stats['hands_dealt']
            vpip_hands = stats['vpip_hands']
            
            # Calculate VPIP percentage
            vpip_percentage = (vpip_hands / hands_dealt * 100) if hands_dealt > 0 else 0
            
            # Calculate profit/loss using buy-ins, cash-outs and final stack
            # Net Profit = Final Stack + Cash Outs - Buy Ins - Admin Adjustments
            # (Admin adjustments are additional money given to player, so subtract from profit)
            actual_profit = stats['final_stack'] + stats['cash_outs'] - stats['buy_ins'] - stats['admin_adjustments']
            
            # Also calculate estimated profit from hand tracking (for comparison)
            estimated_profit = stats['total_winnings'] - stats['total_put_in_pot']
            
            # Get top hand types and betting phases
            top_hand_types = self.get_top_hand_types(stats, 2)
            top_betting_phases = self.get_top_betting_phases(stats, 2)
            
            report[player] = {
                'hands_dealt': hands_dealt,
                'vpip_hands': vpip_hands,
                'vpip_percentage': round(vpip_percentage, 2),
                'buy_ins': round(stats['buy_ins'], 2),
                'admin_adjustments': round(stats['admin_adjustments'], 2),
                'final_stack': round(stats['final_stack'], 2),
                'cash_outs': round(stats['cash_outs'], 2),
                'actual_profit': round(actual_profit, 2),
                'estimated_profit': round(estimated_profit, 2),
                'total_put_in_pot': round(stats['total_put_in_pot'], 2),
                'total_winnings': round(stats['total_winnings'], 2),
                'wins': stats['wins'],
                'top_hand_type': top_hand_types[0][0],
                'top_hand_type_count': top_hand_types[0][1],
                'second_hand_type': top_hand_types[1][0],
                'second_hand_type_count': top_hand_types[1][1],
                'top_betting_phase': top_betting_phases[0][0],
                'top_betting_amount': round(top_betting_phases[0][1], 2),
                'second_betting_phase': top_betting_phases[1][0],
                'second_betting_amount': round(top_betting_phases[1][1], 2)
            }
            
        return report
        
    def print_report(self):
        """Print a formatted report of all player statistics."""
        report = self.generate_report()
        
        print("\n" + "="*120)
        print("POKER VPIP ANALYSIS REPORT")
        print("="*120)
        
        # Sort players by VPIP percentage (descending)
        sorted_players = sorted(report.items(), key=lambda x: x[1]['vpip_percentage'], reverse=True)
        
        print(f"{'Player':<25} {'Hands':<6} {'VPIP':<6} {'VPIP%':<7} {'Buy-In':<8} {'Admin+':<8} {'Stack':<8} {'Profit':<8} {'Wins':<5}")
        print("-" * 120)
        
        for player, stats in sorted_players:
            print(f"{player:<25} {stats['hands_dealt']:<6} {stats['vpip_hands']:<6} "
                  f"{stats['vpip_percentage']:<7.1f}% ${stats['buy_ins']:<7.2f} "
                  f"${stats['admin_adjustments']:<7.2f} ${stats['final_stack']:<7.2f} ${stats['actual_profit']:<7.2f} {stats['wins']:<5}")
                  
        print("\n" + "="*120)
        print("HAND TYPES WON ANALYSIS")
        print("="*120)
        print(f"{'Player':<25} {'Most Won With':<20} {'Count':<6} {'2nd Most Won With':<20} {'Count':<6}")
        print("-" * 120)
        
        for player, stats in sorted_players:
            print(f"{player:<25} {stats['top_hand_type']:<20} {stats['top_hand_type_count']:<6} "
                  f"{stats['second_hand_type']:<20} {stats['second_hand_type_count']:<6}")
                  
        print("\n" + "="*120)
        print("BETTING PHASE ANALYSIS")
        print("="*120)
        print(f"{'Player':<25} {'Most Bet Phase':<15} {'Amount':<10} {'2nd Most Phase':<15} {'Amount':<10}")
        print("-" * 120)
        
        for player, stats in sorted_players:
            print(f"{player:<25} {stats['top_betting_phase']:<15} ${stats['top_betting_amount']:<9.2f} "
                  f"{stats['second_betting_phase']:<15} ${stats['second_betting_amount']:<9.2f}")
        
        print("\n" + "="*120)
        print("DEFINITIONS:")
        print("VPIP = Voluntarily Put In Pot (% of hands where player voluntarily invested money PRE-FLOP only)")
        print("Buy-In = Initial amount bought in during session (approved participation entries only)")
        print("Admin+ = Additional money given by admin (stack updates/adjustments)")
        print("Stack = Final stack amount") 
        print("Profit = Actual profit/loss (Final Stack + Cash Outs - Buy-In - Admin Adjustments)")
        print("Wins = Number of pots won")
        print("Hand Types = The poker hands players won with most frequently")
        print("Betting Phase = When players invested the most money (preflop/flop/turn/river)")
        
    def run_analysis(self):
        """Run the complete analysis."""
        self.load_data()
        self.parse_buy_ins_and_stacks()
        self.parse_hands()
        self.calculate_stats()
        self.print_report()
        return self.generate_report()

# Example usage
if __name__ == "__main__":
    # Replace with your CSV file path
    csv_file_path = "poker_now_log_2025_07_30.csv"
    
    analyzer = PokerVPIPAnalyzer(csv_file_path)
    results = analyzer.run_analysis()
    
    # You can also access individual player stats
    # print(f"\nDetailed stats for a specific player:")
    # player_name = "Connor Dwu @ V-6-EqmFez"  # Replace with actual player name
    # if player_name in results:
    #     stats = results[player_name]
    #     print(f"{player_name}: VPIP = {stats['vpip_percentage']}%, Net Profit = ${stats['actual_profit']}")